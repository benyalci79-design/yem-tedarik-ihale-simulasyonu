import { CommonModule } from '@angular/common';
import { Component, DestroyRef, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { catchError, EMPTY, finalize, forkJoin, switchMap, timer } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ApiService } from '../../core/api.service';
import { Product, SimulationState, TenderSummary } from '../../core/models';
import { numberTr, statusLabel } from '../../shared/display';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <section class="page-heading">
      <div><p class="eyebrow">YÖNETİCİ KONSOLU</p><h1>Simülasyon özeti</h1><p class="lede">Stoktan teslimata kadar devam eden süreci canlı izleyin.</p></div>
      <div class="actions"><button class="button primary" [disabled]="loading || actionLoading || simulation?.is_running" (click)="start()">{{ simulation?.is_running ? 'Simülasyon çalışıyor' : (actionLoading ? 'Başlatılıyor...' : 'Simülasyonu başlat') }}</button><button class="button ghost" [disabled]="loading || actionLoading || !simulation?.is_running" (click)="pause()">{{ actionLoading ? 'İşleniyor...' : 'Duraklat' }}</button></div>
    </section>
    <div *ngIf="error" class="alert">{{ error }} <button class="link-button" (click)="reload()">Yeniden dene</button></div>
    <div *ngIf="loading && !simulation" class="skeleton-grid"><div class="skeleton" *ngFor="let item of [1, 2, 3]"></div></div>

    <ng-container *ngIf="simulation as state">
      <section class="hero-status"><div><span class="eyebrow">SİMÜLASYON SAATİ</span><strong>{{ numberTr(state.elapsed_seconds, 1) }} sn</strong><span class="hero-caption">{{ activityHeadline }}</span></div><span class="run-state" [class.running]="state.is_running">● {{ state.is_running ? 'Çalışıyor' : 'Duraklatıldı' }}</span></section>
      <div *ngIf="state.last_error" class="alert">{{ state.last_error }}</div>
      <section class="flow-card"><div class="section-heading"><div><h2>Canlı süreç akışı</h2><p>{{ activityDescription }}</p></div><span class="live-indicator" [class.paused]="!state.is_running"><i></i>{{ state.is_running ? 'CANLI' : 'DURAKLATILDI' }}</span></div><div class="flow-steps"><div *ngFor="let step of flowSteps; let index = index" class="flow-step" [class.done]="index < flowStep" [class.current]="index === flowStep" [class.pending]="index > flowStep"><span class="step-dot">{{ index < flowStep ? '✓' : index + 1 }}</span><strong>{{ step }}</strong><span>{{ flowStepText(index) }}</span></div></div></section>
      <section class="summary-grid"><article><span>İzlenen ürün</span><strong>{{ products.length }}</strong><small>stok kartı</small></article><article><span>Aktif ihale</span><strong>{{ activeTenders.length }}</strong><small>şu anda işlemde</small></article><article><span>Toplam ihale</span><strong>{{ tenders.length }}</strong><small>simülasyon geçmişi</small></article></section>
      <section class="activity-layout"><div class="activity-card"><div class="section-heading"><div><h2>Son hareketler</h2><p>İhale durumları otomatik olarak güncellenir.</p></div><a routerLink="/tenders" class="text-link">Tümünü gör →</a></div><div *ngIf="recentActivities.length; else noActivity" class="activity-list"><a *ngFor="let activity of recentActivities" class="activity-row" [routerLink]="['/tenders', activity.tender.id]"><span class="activity-icon" [class]="activity.tender.status.toLowerCase()">{{ activity.icon }}</span><span><strong>{{ activity.tender.product_name }} · {{ activity.tender.code }}</strong><small>{{ activity.label }} · {{ numberTr(activity.tender.opened_at_seconds, 1) }} sn'de açıldı</small></span><b>→</b></a></div><ng-template #noActivity><div class="activity-empty">{{ state.is_running ? 'Stok seviyeleri izleniyor; kritik kapsama ulaşınca ilk ihale burada görünecek.' : 'Simülasyonu başlattığınızda süreç hareketleri burada görünecek.' }}</div></ng-template></div><div class="next-card"><span class="eyebrow">SİSTEMİN SIRADAKİ ADIMI</span><strong>{{ nextStep }}</strong><p>{{ nextStepDescription }}</p><a routerLink="/products" class="text-link">Stok ayarlarını incele →</a></div></section>
    </ng-container>

    <section class="section-heading stock-heading"><div><h2>Kritik stok görünümü</h2><p>2 dakikanın altındaki kapsama vurgulanır; sıfır stok ayrıca işaretlenir.</p></div><a routerLink="/tenders" class="text-link">Tüm ihaleleri gör →</a></section>
    <div class="product-grid" *ngIf="products.length; else emptyProducts"><article class="product-card" *ngFor="let product of products" [class.critical]="Number(product.coverage_minutes) < 2" [class.empty]="Number(product.current_stock_kg) === 0"><div class="card-top"><div><span class="code-label">{{ product.code }}</span><h3>{{ product.name }}</h3></div><span *ngIf="Number(product.current_stock_kg) === 0" class="warning-pill">! Stok tükendi</span><span *ngIf="Number(product.current_stock_kg) > 0 && Number(product.coverage_minutes) < 2" class="warning-pill">! Kritik kapsam</span></div><div class="metric-row"><div><span>Mevcut stok</span><strong>{{ numberTr(product.current_stock_kg, 0) }} kg</strong></div><div><span>Kapsama</span><strong>{{ numberTr(product.coverage_minutes, 1) }} dk</strong></div></div><div class="card-foot"><span>{{ numberTr(product.consumption_kg_per_min, 0) }} kg/dk tüketim</span><a *ngIf="product.active_tenders.length" [routerLink]="['/tenders', product.active_tenders[0].id]" class="text-link">{{ product.active_tenders.length }} aktif ihale →</a><span *ngIf="!product.active_tenders.length" class="muted">Aktif ihale yok</span></div></article></div>
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
  loading = true;
  actionLoading = false;
  error = '';
  readonly Number = Number;
  readonly numberTr = numberTr;
  readonly flowSteps = ['Simülasyon', 'Stok analizi', 'İhale açılışı', 'Değerlendirme', 'Teslimat'];

  constructor() { this.startPolling(); }

  get activeTenders(): TenderSummary[] { return this.tenders.filter(tender => ['OPEN', 'EVALUATION', 'AWARDED'].includes(tender.status)); }

  get recentActivities(): { tender: TenderSummary; label: string; icon: string }[] {
    return this.tenders.slice(0, 5).map(tender => ({
      tender,
      label: statusLabel(tender.status),
      icon: tender.status === 'DELIVERED' ? '✓' : tender.status === 'NO_AWARD' ? '—' : tender.status === 'AWARDED' ? '◆' : tender.status === 'EVALUATION' ? '◐' : '●',
    }));
  }

  get flowStep(): number {
    if (!this.simulation) return 0;
    if (this.tenders.some(tender => tender.status === 'AWARDED')) return 4;
    if (this.tenders.some(tender => tender.status === 'EVALUATION')) return 3;
    if (this.tenders.some(tender => tender.status === 'OPEN')) return 2;
    return this.simulation.is_running ? 1 : 0;
  }

  get activityHeadline(): string {
    if (this.activeTenders.some(tender => tender.status === 'EVALUATION')) return 'Teklifler değerlendiriliyor';
    if (this.activeTenders.some(tender => tender.status === 'OPEN')) return 'Açık ihalelerde teklif toplanıyor';
    if (this.activeTenders.some(tender => tender.status === 'AWARDED')) return 'Kazanan teklif için teslimat bekleniyor';
    if (this.simulation?.is_running) return 'Stoklar ve kritik kapsama izleniyor';
    return this.simulation?.elapsed_seconds !== '0.000' ? 'Akış duraklatıldı' : 'Akış başlatılmayı bekliyor';
  }

  get activityDescription(): string {
    if (this.activeTenders.length) return `${this.activeTenders.length} ihale arka planda ilerliyor; durumlar iki saniyede bir yenileniyor.`;
    return this.simulation?.is_running ? 'Motor ürün stoklarını izliyor ve ihtiyaç oluştuğunda ihaleyi otomatik açacak.' : 'Başlat düğmesine bastığınızda simülasyon saati ve otomatik ihale akışı başlayacak.';
  }

  get nextStep(): string {
    if (!this.simulation?.is_running) return 'Simülasyonu başlatın';
    if (this.activeTenders.some(tender => tender.status === 'EVALUATION')) return 'Teklif sonucu oluşacak';
    if (this.activeTenders.some(tender => tender.status === 'OPEN')) return 'NPC teklifleri bekleniyor';
    if (this.activeTenders.some(tender => tender.status === 'AWARDED')) return 'Teslimat zamanı bekleniyor';
    return 'Kritik stok seviyesi bekleniyor';
  }

  get nextStepDescription(): string {
    if (!this.simulation?.is_running) return 'Akışı başlattığınızda sistem stokları otomatik izlemeye başlayacak.';
    if (this.activeTenders.length) return 'İhale zamanlayıcısı ilerliyor; yeni gelişmeler son hareketler alanına düşecek.';
    return 'Kritik kapsama ulaşıldığında ürün için yeni ihale otomatik oluşturulur.';
  }

  flowStepText(index: number): string {
    if (index < this.flowStep) return 'Tamamlandı';
    if (index === this.flowStep) return index === 0 && !this.simulation?.is_running ? 'Bekliyor' : 'Şu an';
    return 'Sırada';
  }

  reload(): void {
    this.loading = true;
    this.loadSnapshot().subscribe({ next: snapshot => this.applySnapshot(snapshot), error: () => this.showLoadError() });
  }

  start(): void {
    if (this.actionLoading || this.loading || this.simulation?.is_running) return;
    this.actionLoading = true;
    this.error = '';
    this.api.startSimulation().pipe(finalize(() => this.actionLoading = false)).subscribe({ next: state => { this.simulation = state; this.loading = false; }, error: () => this.error = 'Simülasyon başlatılamadı. Backend bağlantısını kontrol edin.' });
  }

  pause(): void {
    if (this.actionLoading || this.loading || !this.simulation?.is_running) return;
    this.actionLoading = true;
    this.error = '';
    this.api.pauseSimulation().pipe(finalize(() => this.actionLoading = false)).subscribe({ next: state => { this.simulation = state; this.loading = false; }, error: () => this.error = 'Simülasyon duraklatılamadı. Backend bağlantısını kontrol edin.' });
  }

  private startPolling(): void {
    timer(0, 2000).pipe(switchMap(() => this.loadSnapshot().pipe(catchError(() => { this.showLoadError(); return EMPTY; }))), takeUntilDestroyed(this.destroyRef)).subscribe(snapshot => this.applySnapshot(snapshot));
  }

  private loadSnapshot() { return forkJoin({ simulation: this.api.simulation(), products: this.api.products(), tenders: this.api.tenders() }); }

  private applySnapshot(snapshot: { simulation: SimulationState; products: { items: Product[] }; tenders: { items: TenderSummary[] } }): void {
    this.simulation = snapshot.simulation;
    this.products = snapshot.products.items;
    this.tenders = snapshot.tenders.items;
    this.loading = false;
    this.error = '';
  }

  private showLoadError(): void { this.error = 'Backend bağlantısını kontrol edin.'; this.loading = false; }
}
