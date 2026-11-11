import { CommonModule } from '@angular/common';
import { Component, DestroyRef, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { catchError, EMPTY, finalize, forkJoin, switchMap, timer } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ApiService } from '../../core/api.service';
import {
  ChartSeries,
  HistoryPoint,
  Product,
  SimulationState,
  StockMetrics,
  TenderSummary,
} from '../../core/models';
import { numberTr, statusLabel } from '../../shared/display';import { LineChartComponent } from '../../shared/line-chart.component';

// Renk körlüğüne dayanıklı palet (Okabe-Ito) + farklı çizgi deseni ve işaretçi.
const CHART_COLORS = ['#0072B2', '#E69F00', '#009E73', '#CC79A7', '#56B4E9', '#D55E00'];
const CHART_DASHES = ['', '8 5', '2 4', '12 4 2 4', '10 6', '4 3'];
const CHART_MARKERS: ChartSeries['marker'][] = ['circle', 'square', 'triangle', 'circle', 'square', 'triangle'];

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink, LineChartComponent],
  template: `
    <section class="page-heading">
      <div><p class="eyebrow">YÖNETİCİ KONSOLU</p><h1>Simülasyon özeti</h1><p class="lede">Stoktan teslimata kadar devam eden süreci canlı izleyin.</p></div>
      <div class="heading-meta" *ngIf="simulation">
        <span class="speed-chip">{{ simulation.is_running ? (numberTr(Number(simulation.speed), 1) + 'x hız') : 'Duraklatıldı' }}</span>
      </div>
    </section>
    <div *ngIf="error" class="alert">{{ error }} <button class="link-button" (click)="reload()">Yeniden dene</button></div>
    <div *ngIf="loading && !simulation" class="skeleton-grid"><div class="skeleton" *ngFor="let item of [1, 2, 3]"></div></div>

    <ng-container *ngIf="simulation as state">
      <section class="hero-status"><div><span class="eyebrow">SİMÜLASYON SAATİ</span><strong>{{ numberTr(displayElapsedSeconds, 1) }} sn</strong><span class="hero-caption">{{ activityHeadline }}</span></div><span class="run-state" [class.running]="state.is_running">● {{ state.is_running ? 'Çalışıyor' : 'Duraklatıldı' }}</span></section>
      <div *ngIf="state.last_error" class="alert">{{ state.last_error }}</div>

      <section class="summary-grid">
        <article><span>İzlenen ürün</span><strong>{{ products.length }}</strong><small>stok kartı</small></article>
        <article><span>Aktif ihale</span><strong>{{ activeTenders.length }}</strong><small>şu anda işlemde</small></article>
        <article><span>Toplam ihale</span><strong>{{ tenders.length }}</strong><small>simülasyon geçmişi</small></article>
      </section>

      <section class="section-heading cost-heading">
        <div><h2>Stok maliyeti</h2><p>Ağırlıklı ortalama maliyet; teslimat geldikçe birim maliyet değişir, tüketim yalnızca stoğu düşürür.</p></div>
      </section>
      <div class="cost-grid">
        <article class="cost-card" *ngFor="let item of metrics?.items || []">
          <span class="code-label">{{ item.product_code ?? item.product_name }}</span>
          <strong>{{ numberTr(item.value_tl, 0) }} TL</strong>
          <div class="cost-meta"><span>{{ numberTr(item.stock_kg, 0) }} kg</span><span>{{ numberTr(item.avg_cost_per_kg, 2) }} TL/kg</span></div>
        </article>
        <article class="cost-card total" *ngIf="metrics">
          <span class="code-label">TOPLAM</span>
          <strong>{{ numberTr(metrics.total_value_tl, 0) }} TL</strong>
          <div class="cost-meta"><span>{{ numberTr(metrics.total_stock_kg, 0) }} kg</span><span>{{ numberTr(metrics.total_avg_cost_per_kg, 2) }} TL/kg</span></div>
        </article>
      </div>

      <div class="chart-grid">
        <section class="chart-block">
          <h3>Stok maliyeti (TL)</h3>
          <app-line-chart [series]="valueSeries" [xLabels]="chartLabels" [digits]="0" ariaLabel="Stok maliyeti zaman serisi" emptyText="Maliyet geçmişi simülasyon ilerledikçe oluşur." />
        </section>
        <section class="chart-block">
          <h3>Birim maliyet (TL/kg)</h3>
          <app-line-chart [series]="unitCostSeries" [xLabels]="chartLabels" [digits]="2" ariaLabel="Birim maliyet zaman serisi" emptyText="Birim maliyet geçmişi simülasyon ilerledikçe oluşur." />
        </section>
      </div>

      <section class="flow-card"><div class="section-heading"><div><h2>Canlı süreç akışı</h2><p>{{ activityDescription }}</p></div><span class="live-indicator" [class.paused]="!state.is_running"><i></i>{{ state.is_running ? 'CANLI' : 'DURAKLATILDI' }}</span></div><div class="flow-steps"><div *ngFor="let step of flowSteps; let index = index" class="flow-step" [class.done]="index < flowStep" [class.current]="index === flowStep" [class.pending]="index > flowStep"><span class="step-dot">{{ index < flowStep ? '✓' : index + 1 }}</span><strong>{{ step }}</strong><span>{{ flowStepText(index) }}</span></div></div></section>
      <section class="activity-layout"><div class="activity-card"><div class="section-heading"><div><h2>Son hareketler</h2><p>İhale durumları iki saniyede bir yenilenir.</p></div><a routerLink="/tenders" class="text-link">Tümünü gör →</a></div><div *ngIf="recentActivities.length; else noActivity" class="activity-list"><a *ngFor="let activity of recentActivities" class="activity-row" [routerLink]="['/tenders', activity.tender.id]"><span class="activity-icon" [class]="activity.tender.status.toLowerCase()">{{ activity.icon }}</span><span><strong>{{ activity.tender.product_name }} · {{ activity.tender.code }}</strong><small>{{ activity.label }} · {{ numberTr(activity.tender.opened_at_seconds, 1) }} sn'de açıldı</small></span><b>→</b></a></div><ng-template #noActivity><div class="activity-empty">{{ state.is_running ? 'Yeni ihale açmak için İhale Listesi ekranını kullanın.' : 'Simülasyonu üst bardan başlattığınızda süreç hareketleri burada görünecek.' }}</div></ng-template></div><div class="next-card"><span class="eyebrow">SİSTEMİN SIRADAKİ ADIMI</span><strong>{{ nextStep }}</strong><p>{{ nextStepDescription }}</p><a routerLink="/tenders" class="text-link">İhale listesine git →</a></div></section>
    </ng-container>

    <section class="section-heading stock-heading"><div><h2>Kritik stok görünümü</h2><p>Doluluk = (stok + yoldaki) / depo kapasitesi. 2 dakikanın altındaki kapsama vurgulanır.</p></div><a routerLink="/tenders" class="text-link">Tüm ihaleleri gör →</a></section>
    <div class="product-grid" *ngIf="products.length; else emptyProducts"><article class="product-card" *ngFor="let product of products" [class.critical]="Number(product.coverage_minutes) < 2" [class.empty]="Number(product.current_stock_kg) === 0"><div class="card-top"><div><span class="code-label">{{ product.code }}</span><h3>{{ product.name }}</h3></div><span *ngIf="Number(product.current_stock_kg) === 0" class="warning-pill">! Stok tükendi</span><span *ngIf="Number(product.current_stock_kg) > 0 && Number(product.coverage_minutes) < 2" class="warning-pill">! Kritik kapsam</span></div><div class="metric-row"><div><span>Mevcut stok</span><strong>{{ numberTr(product.current_stock_kg, 0) }} kg</strong></div><div><span>Kapsama</span><strong>{{ numberTr(product.coverage_minutes, 1) }} dk</strong></div></div><div class="capacity-row"><div class="capacity-bar"><span [style.width.%]="fillPercent(product)"></span></div><small>{{ numberTr(product.current_stock_kg, 0) }} + {{ numberTr(product.incoming_kg, 0) }} yolda / {{ numberTr(product.capacity_kg, 0) }} kg (%{{ numberTr(fillPercent(product), 0) }})</small></div><div class="card-foot"><span>{{ numberTr(product.consumption_kg_per_min, 0) }} kg/dk · {{ numberTr(product.avg_cost_per_kg, 2) }} TL/kg</span><a *ngIf="product.active_tenders.length" [routerLink]="['/tenders', product.active_tenders[0].id]" class="text-link">{{ product.active_tenders.length }} aktif ihale →</a><span *ngIf="!product.active_tenders.length" class="muted">Aktif ihale yok</span></div></article></div>
    <ng-template #emptyProducts><div class="empty-state"><strong>Henüz ürün verisi yok</strong><span>Seed tamamlandığında ürün kartları burada görünecek.</span></div></ng-template>
  `,
  styleUrl: './dashboard.component.css',
})
export class DashboardComponent {
  private readonly api = inject(ApiService);
  private readonly destroyRef = inject(DestroyRef);
  simulation: SimulationState | null = null;
  products: Product[] = [];
  tenders: TenderSummary[] = [];
  metrics: StockMetrics | null = null;
  history: HistoryPoint[] = [];
  loading = true;
  error = '';
  displayElapsedSeconds = 0;
  private elapsedAnchorSeconds = 0;
  private elapsedAnchorTime = performance.now();
  readonly Number = Number;
  readonly numberTr = numberTr;
  readonly flowSteps = ['Simülasyon', 'Stok analizi', 'İhale açılışı', 'Değerlendirme', 'Teslimat'];

  constructor() {
    this.startPolling();
    this.startDisplayClock();
    this.startMetricsPolling();
  }

  get activeTenders(): TenderSummary[] {
    return this.tenders.filter((tender) => ['OPEN', 'EVALUATION', 'AWARDED'].includes(tender.status));
  }

  get recentActivities(): { tender: TenderSummary; label: string; icon: string }[] {
    return this.tenders.slice(0, 5).map((tender) => ({
      tender,
      label: statusLabel(tender.status),
      icon: tender.status === 'DELIVERED' ? '✓' : tender.status === 'NO_AWARD' ? '—' : tender.status === 'AWARDED' ? '◆' : tender.status === 'EVALUATION' ? '◐' : '●',
    }));
  }

  get flowStep(): number {
    if (!this.simulation) return 0;
    if (this.tenders.some((tender) => tender.status === 'AWARDED')) return 4;
    if (this.tenders.some((tender) => tender.status === 'EVALUATION')) return 3;
    if (this.tenders.some((tender) => tender.status === 'OPEN')) return 2;
    return this.simulation.is_running ? 1 : 0;
  }

  get activityHeadline(): string {
    if (this.activeTenders.some((tender) => tender.status === 'EVALUATION')) return 'Teklifleri inceleyip kabul etmeniz bekleniyor';
    if (this.activeTenders.some((tender) => tender.status === 'OPEN')) return 'Açık ihalelerde teklif toplanıyor';
    if (this.activeTenders.some((tender) => tender.status === 'AWARDED')) return 'Kazanan teklifler için teslimat sürüyor';
    if (this.simulation?.is_running) return 'Stoklar ve kritik kapsama izleniyor';
    return this.simulation?.elapsed_seconds !== '0.000' ? 'Akış duraklatıldı' : 'Akış başlatılmayı bekliyor';
  }

  get activityDescription(): string {
    if (this.activeTenders.length) return `${this.activeTenders.length} ihale arka planda ilerliyor; durumlar iki saniyede bir yenileniyor.`;
    return this.simulation?.is_running ? 'Yeni ihale açmak için İhale Listesi ekranındaki "Yeni ihale aç" panelini kullanın.' : 'Üst bardaki hız düğmeleriyle simülasyonu başlatın.';
  }

  get nextStep(): string {
    if (!this.simulation?.is_running) return 'Simülasyonu başlatın';
    if (this.activeTenders.some((tender) => tender.status === 'EVALUATION')) return 'Teklifleri kabul edin';
    if (this.activeTenders.some((tender) => tender.status === 'OPEN')) return 'NPC teklifleri bekleniyor';
    if (this.activeTenders.some((tender) => tender.status === 'AWARDED')) return 'Teslimat bekleniyor';
    return 'Yeni ihale açabilirsiniz';
  }

  get nextStepDescription(): string {
    if (!this.simulation?.is_running) return 'Hız düğmelerinden birine bastığınızda simülasyon saati ilerlemeye başlar.';
    if (this.activeTenders.length) return 'Süre dolduğunda teklifler açılır; kabul ettiğiniz miktarlar teslimata dönüşür.';
    return 'Kritik kapsamaya düşen ürün için İhale Listesi ekranından ihale açın.';
  }

  get chartLabels(): string[] {
    return this.history.map((point) => `${numberTr(point.elapsed_seconds, 0)} sn`);
  }

  get valueSeries(): ChartSeries[] {
    return this.buildSeries((item) => item.value_tl, (point) => point.total_value_tl);
  }

  get unitCostSeries(): ChartSeries[] {
    return this.buildSeries((item) => item.avg_cost_per_kg, (point) => point.total_avg_cost_per_kg);
  }

  flowStepText(index: number): string {
    if (index < this.flowStep) return 'Tamamlandı';
    if (index === this.flowStep) return index === 0 && !this.simulation?.is_running ? 'Bekliyor' : 'Şu an';
    return 'Sırada';
  }

  fillPercent(product: Product): number {
    const capacity = Number(product.capacity_kg);
    if (!capacity) return 0;
    const used = Number(product.current_stock_kg) + Number(product.incoming_kg);
    return Math.max(0, Math.min(100, (used / capacity) * 100));
  }

  reload(): void {
    this.loading = true;
    this.loadSnapshot().subscribe({ next: (snapshot) => this.applySnapshot(snapshot), error: () => this.showLoadError() });
  }

  private startPolling(): void {
    timer(0, 2000)
      .pipe(
        switchMap(() => this.loadSnapshot().pipe(catchError(() => { this.showLoadError(); return EMPTY; }))),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((snapshot) => this.applySnapshot(snapshot));
  }

  private startDisplayClock(): void {
    timer(0, 250)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => {
        if (!this.simulation) return;
        const speed = Number(this.simulation.speed) || 1;
        const runningSeconds = this.simulation.is_running ? ((performance.now() - this.elapsedAnchorTime) / 1000) * speed : 0;
        this.displayElapsedSeconds = Math.max(0, this.elapsedAnchorSeconds + runningSeconds);
      });
  }

  private startMetricsPolling(): void {
    timer(0, 5000)
      .pipe(
        switchMap(() => {
          // Simülasyon dururken aynı geçmişi tekrar tekrar çizmeyelim.
          if (this.simulation && !this.simulation.is_running && this.history.length > 0) return EMPTY;
          return forkJoin({ metrics: this.api.stockMetrics(), history: this.api.stockHistory(300) }).pipe(
            catchError(() => EMPTY),
          );
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((result) => {
        this.metrics = result.metrics;
        this.history = result.history.items;
      });
  }

  private loadSnapshot() {
    return forkJoin({ simulation: this.api.simulation(), products: this.api.products(), tenders: this.api.tenders() });
  }

  private applySnapshot(snapshot: { simulation: SimulationState; products: { items: Product[] }; tenders: { items: TenderSummary[] } }): void {
    this.setSimulation(snapshot.simulation);
    this.products = snapshot.products.items;
    this.tenders = snapshot.tenders.items;
    this.loading = false;
    this.error = '';
  }

  private showLoadError(): void {
    this.error = 'Backend bağlantısını kontrol edin.';
    this.loading = false;
  }

  private setSimulation(state: SimulationState): void {
    const server = Number(state.elapsed_seconds) || 0;
    const speed = Number(state.speed) || 1;
    const local = this.displayElapsedSeconds;
    this.simulation = state;
    if (!state.is_running) {
      this.elapsedAnchorSeconds = server;
    } else {
      const drift = local - server;
      this.elapsedAnchorSeconds = drift > speed * 2 || drift < -speed * 3 ? server : Math.max(server, local);
    }
    this.elapsedAnchorTime = performance.now();
    this.displayElapsedSeconds = this.elapsedAnchorSeconds;
  }

  private buildSeries(
    pick: (item: { value_tl: string; avg_cost_per_kg: string }) => string,
    total: (point: HistoryPoint) => string,
  ): ChartSeries[] {
    const first = this.history[0];
    if (!first) return [];
    const series: ChartSeries[] = first.products.map((product, index) => ({
      id: `product-${product.product_id}`,
      label: product.product_name,
      color: CHART_COLORS[index % CHART_COLORS.length],
      dash: CHART_DASHES[index % CHART_DASHES.length],
      marker: CHART_MARKERS[index % CHART_MARKERS.length],
      values: this.history.map((point) => {
        const item = point.products.find((candidate) => candidate.product_id === product.product_id);
        return item ? Number(pick(item)) : 0;
      }),
    }));
    series.push({
      id: 'total',
      label: 'Toplam',
      color: '#111827',
      dash: '10 4',
      marker: 'triangle',
      values: this.history.map((point) => Number(total(point))),
    });
    return series;
  }
}
