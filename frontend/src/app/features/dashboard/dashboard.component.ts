import { CommonModule } from '@angular/common';
import { Component, DestroyRef, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { catchError, EMPTY, forkJoin, switchMap, timer } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ApiService } from '../../core/api.service';
import { Product, SimulationState } from '../../core/models';
import { numberTr } from '../../shared/display';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <section class="page-heading"><div><p class="eyebrow">YÖNETİCİ KONSOLU</p><h1>Simülasyon özeti</h1><p class="lede">Stok, aktif ihaleler ve simülasyon saati tek bakışta.</p></div><div class="actions"><button class="button primary" [disabled]="loading || simulation?.is_running" (click)="start()">{{ simulation?.is_running ? 'Simülasyon çalışıyor' : 'Simülasyonu başlat' }}</button><button class="button ghost" [disabled]="loading || !simulation?.is_running" (click)="pause()">Duraklat</button></div></section>
    <div *ngIf="error" class="alert">{{ error }} <button class="link-button" (click)="reload()">Yeniden dene</button></div>
    <div *ngIf="loading && !simulation" class="skeleton-grid"><div class="skeleton" *ngFor="let item of [1,2,3]"></div></div>
    <ng-container *ngIf="simulation as state"><section class="hero-status"><div><span class="eyebrow">SİMÜLASYON SAATİ</span><strong>{{ numberTr(state.elapsed_seconds, 1) }} sn</strong></div><span class="run-state" [class.running]="state.is_running">● {{ state.is_running ? 'Çalışıyor' : 'Duraklatıldı' }}</span></section><div *ngIf="state.last_error" class="alert">{{ state.last_error }}</div></ng-container>
    <section class="section-heading"><div><h2>Kritik stok görünümü</h2><p>2 dakikanın altındaki kapsama vurgulanır; sıfır stok ayrıca işaretlenir.</p></div><a routerLink="/tenders" class="text-link">Tüm ihaleleri gör →</a></section>
    <div class="product-grid" *ngIf="products.length; else emptyProducts"><article class="product-card" *ngFor="let product of products" [class.critical]="Number(product.coverage_minutes) < 2" [class.empty]="Number(product.current_stock_kg) === 0"><div class="card-top"><div><span class="code-label">{{ product.code }}</span><h3>{{ product.name }}</h3></div><span *ngIf="Number(product.current_stock_kg) === 0" class="warning-pill">! Stok tükendi</span><span *ngIf="Number(product.current_stock_kg) > 0 && Number(product.coverage_minutes) < 2" class="warning-pill">! Kritik kapsam</span></div><div class="metric-row"><div><span>Mevcut stok</span><strong>{{ numberTr(product.current_stock_kg, 0) }} kg</strong></div><div><span>Kapsama</span><strong>{{ numberTr(product.coverage_minutes, 1) }} dk</strong></div></div><div class="card-foot"><span>{{ numberTr(product.consumption_kg_per_min, 0) }} kg/dk tüketim</span><a *ngIf="product.active_tenders.length" [routerLink]="['/tenders', product.active_tenders[0].id]" class="text-link">{{ product.active_tenders.length }} aktif ihale →</a><span *ngIf="!product.active_tenders.length" class="muted">Aktif ihale yok</span></div></article></div>
    <ng-template #emptyProducts><div class="empty-state"><strong>Henüz ürün verisi yok</strong><span>Seed tamamlandığında ürün kartları burada görünecek.</span></div></ng-template>
  `,
  styles: ['.page-heading,.section-heading,.card-top,.card-foot,.hero-status,.actions,.metric-row{display:flex;align-items:center;justify-content:space-between;gap:1rem}.page-heading{margin-bottom:2rem;align-items:flex-end}.eyebrow,.code-label{color:#1d4ed8;font-size:.78rem;font-weight:800;letter-spacing:.08em}.page-heading h1{margin:.3rem 0;font-size:clamp(2rem,4vw,3rem);color:#111827}.lede,.section-heading p{margin:.35rem 0 0;color:#4b5563}.button{border:0;border-radius:.7rem;padding:.8rem 1.1rem;font-weight:750;cursor:pointer}.primary{color:#fff;background:#1d4ed8}.ghost{color:#1e3a8a;background:#dbeafe}.hero-status{padding:1.25rem 1.5rem;background:#111827;color:#fff;border-radius:1rem;margin-bottom:2rem}.hero-status strong{display:block;font-size:2rem;margin-top:.25rem;color:#fff}.hero-status .eyebrow{color:#bfdbfe}.run-state{padding:.55rem .8rem;background:#374151;border-radius:999px;font-weight:750}.run-state.running{background:#047857}.section-heading{margin-bottom:1rem}.section-heading h2{margin:0;color:#111827}.text-link{color:#1d4ed8;font-weight:750;text-decoration:none}.product-grid,.skeleton-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem}.product-card{min-height:210px;padding:1.25rem;background:#fff;border:1px solid #cbd5e1;border-radius:1rem}.product-card.critical{border:2px solid #e11d48;background:#fff1f2}.product-card h3{margin:.3rem 0 0;color:#111827;font-size:1.3rem}.warning-pill{color:#9f1239;background:#fecdd3;border-radius:999px;padding:.3rem .55rem;font-size:.8rem;font-weight:800}.metric-row{margin:2rem 0 1.2rem;justify-content:flex-start;gap:2.5rem}.metric-row div{display:grid;gap:.35rem}.metric-row span,.card-foot,.muted{color:#4b5563}.metric-row strong{color:#111827;font-size:1.65rem}.card-foot{border-top:1px solid #e5e7eb;padding-top:.9rem;font-size:.9rem}.alert{padding:.9rem 1rem;border-radius:.7rem;margin-bottom:1rem;color:#991b1b;background:#fee2e2;border:1px solid #fca5a5}.link-button{border:0;background:transparent;color:#991b1b;text-decoration:underline;cursor:pointer}.skeleton{height:210px;border-radius:1rem;background:#e5e7eb}.empty-state{display:grid;gap:.35rem;padding:2rem;text-align:center;background:#fff;border:1px dashed #64748b;border-radius:1rem;color:#334155}.empty-state strong{color:#111827;font-size:1.1rem}@media(max-width:800px){.product-grid,.skeleton-grid{grid-template-columns:1fr}.page-heading,.section-heading{align-items:flex-start;flex-direction:column}.actions{width:100%}}']
})
export class DashboardComponent {
  private readonly api = inject(ApiService);
  private readonly destroyRef = inject(DestroyRef);
  simulation: SimulationState | null = null;
  products: Product[] = [];
  loading = true;
  error = '';
  readonly Number = Number;
  readonly numberTr = numberTr;

  constructor() { this.reload(); }

  reload(): void {
    this.loading = true;
    timer(0, 2000).pipe(
      switchMap(() => forkJoin({ simulation: this.api.simulation(), products: this.api.products() })),
      catchError(() => { this.error = 'Backend bağlantısını kontrol edin.'; this.loading = false; return EMPTY; }),
      takeUntilDestroyed(this.destroyRef)
    ).subscribe(({ simulation, products }) => {
      this.simulation = simulation;
      this.products = products.items;
      this.loading = false;
      this.error = '';
    });
  }

  start(): void { this.api.startSimulation().subscribe(() => this.reload(), () => this.error = 'Simülasyon başlatılamadı.'); }
  pause(): void { this.api.pauseSimulation().subscribe(() => this.reload(), () => this.error = 'Simülasyon duraklatılamadı.'); }
}
