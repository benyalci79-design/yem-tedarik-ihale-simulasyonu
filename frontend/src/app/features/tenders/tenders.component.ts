import { CommonModule } from '@angular/common';
import { Component, DestroyRef, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { catchError, EMPTY, switchMap, timer } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ApiService } from '../../core/api.service';
import { Product, TenderSummary } from '../../core/models';
import { numberTr } from '../../shared/display';
import { StatusBadgeComponent } from '../../shared/status-badge.component';

@Component({
  selector: 'app-tenders',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink, StatusBadgeComponent],
  template: `<section class="page-heading"><div><p class="eyebrow">SÜREÇ İZLEME</p><h1>İhale listesi</h1><p class="lede">Açık teklifler, değerlendirme ve teslim geçmişini izleyin.</p></div></section><form class="filters" [formGroup]="filters"><label>Ürün<select formControlName="productId"><option [ngValue]="null">Tüm ürünler</option><option *ngFor="let product of products" [ngValue]="product.id">{{ product.name }}</option></select></label><label>Aşama<select formControlName="status"><option value="">Tüm aşamalar</option><option value="OPEN">Açık</option><option value="EVALUATION">Değerlendirmede</option><option value="AWARDED">Teslim bekliyor</option><option value="DELIVERED">Teslim edildi</option><option value="NO_AWARD">Sonuçsuz</option></select></label></form><div *ngIf="error" class="alert">{{ error }} <button class="link-button" (click)="load()">Yeniden dene</button></div><div class="table" *ngIf="tenders.length"><div class="table-head"><span>İhale</span><span>Ürün</span><span>Miktar</span><span>Aşama</span><span>Kalan</span><span></span></div><a class="table-row" *ngFor="let tender of tenders" [routerLink]="['/tenders', tender.id]"><div><strong>{{ tender.code }}</strong><small>{{ tender.offer_count }}/{{ tender.invited_count }} teklif</small></div><span>{{ tender.product_name }}</span><strong>{{ numberTr(tender.quantity_ton, 3) }} ton</strong><app-status-badge [status]="tender.status"></app-status-badge><span>{{ numberTr(tender.remaining_seconds, 1) }} sn</span><span class="arrow">→</span></a></div><div class="empty-state" *ngIf="!loading && !tenders.length"><strong>Henüz ihale yok</strong><span>Simülasyonu başlatın; kritik kapsama ulaşınca ihaleler otomatik açılır.</span></div><div class="loading" *ngIf="loading">İhale listesi yükleniyor…</div>`,
  styles: ['.page-heading { margin-bottom:2rem; }.eyebrow { color:#1d4ed8; font-size:.78rem; font-weight:800; letter-spacing:.08em; }.page-heading h1 { margin:.3rem 0; color:#111827; font-size:2.4rem; }.lede { color:#4b5563; }.filters { display:flex; gap:1rem; padding:1rem; margin-bottom:1rem; background:#fff; border:1px solid #cbd5e1; border-radius:.8rem; }.filters label { display:grid; gap:.35rem; color:#374151; font-weight:750; }.filters select { min-width:13rem; border:1px solid #64748b; border-radius:.45rem; padding:.6rem; color:#111827; background:#fff; }.table { background:#fff; border:1px solid #cbd5e1; border-radius:1rem; overflow:hidden; }.table-head,.table-row { display:grid; grid-template-columns:1.5fr 1.5fr 1fr 1.6fr 1fr 40px; gap:1rem; align-items:center; padding:1rem 1.2rem; }.table-head { color:#374151; background:#f1f5f9; font-weight:800; font-size:.85rem; }.table-row { color:#172033; text-decoration:none; border-top:1px solid #e5e7eb; }.table-row:hover { background:#eff6ff; }.table-row strong,.table-row small { display:block; }.table-row small { color:#4b5563; margin-top:.25rem; }.arrow { color:#1d4ed8; font-size:1.3rem; text-align:right; }.alert { padding:.9rem 1rem; color:#991b1b; background:#fee2e2; border:1px solid #fca5a5; border-radius:.7rem; margin-bottom:1rem; }.link-button { border:0; background:transparent; color:#991b1b; text-decoration:underline; cursor:pointer; }.empty-state,.loading { padding:2.5rem; text-align:center; color:#334155; background:#fff; border:1px dashed #64748b; border-radius:1rem; }.empty-state strong,.empty-state span { display:block; }.empty-state span { margin-top:.35rem; } @media(max-width:850px){.table-head{display:none}.table-row{grid-template-columns:1fr 1fr; gap:.65rem}.table-row .status-badge{justify-self:start}.filters{flex-direction:column}.filters select{width:100%}}']
})
export class TendersComponent {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  private readonly destroyRef = inject(DestroyRef);
  products: Product[] = [];
  tenders: TenderSummary[] = [];
  loading = true;
  error = '';
  readonly numberTr = numberTr;
  readonly filters = this.fb.group({ productId: [null as number | null], status: [''] });

  constructor() {
    this.api.products().subscribe(result => this.products = result.items);
    this.filters.valueChanges.subscribe(() => this.load());
    this.load();
  }

  load(): void {
    this.loading = true;
    const value = this.filters.getRawValue();
    timer(0, 2000).pipe(
      switchMap(() => this.api.tenders(value.productId ?? undefined, value.status || undefined)),
      catchError(() => { this.error = 'İhaleler yüklenemedi.'; this.loading = false; return EMPTY; }),
      takeUntilDestroyed(this.destroyRef)
    ).subscribe(result => { this.tenders = result.items; this.loading = false; this.error = ''; });
  }
}
