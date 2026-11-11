import { CommonModule } from '@angular/common';
import { Component, DestroyRef, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { catchError, EMPTY, finalize, forkJoin, merge, Subject, switchMap, timer } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ApiService, apiErrorMessage } from '../../core/api.service';
import { Product, TenderSummary } from '../../core/models';
import { numberTr } from '../../shared/display';
import { StatusBadgeComponent } from '../../shared/status-badge.component';

@Component({
  selector: 'app-tenders',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink, StatusBadgeComponent],
  template: `
    <section class="page-heading"><div><p class="eyebrow">SÜREÇ İZLEME</p><h1>İhale listesi</h1><p class="lede">İhaleyi siz açarsınız, NPC tekliflerini siz kabul edersiniz.</p></div></section>

    <section class="new-tender">
      <div class="section-heading"><div><h2>Yeni ihale aç</h2><p>Miktar, ürünün boş depo kapasitesini aşamaz; aynı üründe tek aktif ihale olabilir.</p></div></div>
      <form [formGroup]="createForm" (ngSubmit)="createTender()" class="create-form">
        <label>Ürün
          <select formControlName="productId">
            <option [ngValue]="null">Ürün seçin</option>
            <option *ngFor="let product of products" [ngValue]="product.id">{{ product.name }}</option>
          </select>
        </label>
        <label>Miktar (ton)
          <input type="number" formControlName="quantityTon" min="0.001" step="0.001" placeholder="örn. 2.100">
        </label>
        <button type="button" class="button ghost" [disabled]="!selectedProduct" (click)="useSuggested()">
          Önerilen: {{ selectedProduct ? numberTr(selectedProduct.suggested_quantity_ton, 3) : '—' }} ton
        </button>
        <button type="submit" class="button primary" [disabled]="creating || !selectedProduct || hasActiveTender">İhale aç</button>
      </form>
      <p class="hint" *ngIf="selectedProduct">
        Stok {{ numberTr(selectedProduct.current_stock_kg, 0) }} kg · Yolda {{ numberTr(selectedProduct.incoming_kg, 0) }} kg ·
        Boş kapasite {{ numberTr(selectedProduct.free_capacity_kg, 0) }} kg
      </p>
      <p class="error" *ngIf="hasActiveTender">Bu üründe açık bir ihale veya süren teslimat var; önce onu tamamlayın.</p>
      <p class="error" *ngIf="createError">{{ createError }}</p>
    </section>

    <form class="filters" [formGroup]="filters"><label>Ürün<select formControlName="productId"><option [ngValue]="null">Tüm ürünler</option><option *ngFor="let product of products" [ngValue]="product.id">{{ product.name }}</option></select></label><label>Aşama<select formControlName="status"><option value="">Tüm aşamalar</option><option value="OPEN">Teklif toplanıyor</option><option value="EVALUATION">Karar bekliyor</option><option value="AWARDED">Teslimatta</option><option value="DELIVERED">Teslim edildi</option><option value="NO_AWARD">Sonuçsuz</option></select></label></form>
    <div *ngIf="error" class="alert">{{ error }} <button class="link-button" (click)="load()">Yeniden dene</button></div>
    <div class="table" *ngIf="tenders.length">
      <div class="table-head"><span>İhale</span><span>Ürün</span><span>Miktar</span><span>Aşama</span><span>Kalan</span><span>Kabul</span><span></span></div>
      <a class="table-row" *ngFor="let tender of tenders" [routerLink]="['/tenders', tender.id]"><div><strong>{{ tender.code }}</strong><small>{{ tender.offer_count }}/{{ tender.invited_count }} teklif</small></div><span>{{ tender.product_name }}</span><strong>{{ numberTr(tender.quantity_ton, 3) }} ton</strong><app-status-badge [status]="tender.status"></app-status-badge><span>{{ numberTr(tender.remaining_seconds, 1) }} sn</span><span class="accepted">{{ numberTr(tender.accepted_total_kg, 0) }} / {{ quantityKg(tender) }} kg</span><span class="arrow">→</span></a>
    </div>
    <div class="empty-state" *ngIf="!loading && !tenders.length"><strong>Henüz ihale yok</strong><span>Yukarıdaki panelden ilk ihaleyi açın.</span></div>
    <div class="loading" *ngIf="loading && !tenders.length">İhale listesi hazırlanıyor…</div>
  `,
  styles: [
    '.page-heading { margin-bottom:2rem; }.eyebrow { color:#1d4ed8; font-size:.78rem; font-weight:800; letter-spacing:.08em; }.page-heading h1 { margin:.3rem 0; color:#111827; font-size:2.4rem; }.lede { color:#4b5563; }',
    '.new-tender { background:#fff; border:1px solid #cbd5e1; border-radius:1rem; padding:1.1rem 1.25rem; margin-bottom:1.25rem; }',
    '.new-tender .section-heading { display:flex; justify-content:space-between; gap:1rem; align-items:flex-end; margin-bottom:.9rem; }',
    '.new-tender h2 { margin:0; color:#111827; }.new-tender p { margin:.3rem 0 0; color:#4b5563; }',
    '.create-form { display:flex; flex-wrap:wrap; gap:.8rem; align-items:flex-end; }',
    '.create-form label { display:grid; gap:.35rem; color:#374151; font-weight:750; font-size:.9rem; }',
    '.create-form select, .create-form input { border:1px solid #64748b; border-radius:.5rem; padding:.6rem; color:#111827; background:#fff; min-width:12rem; }',
    '.button { border:0; border-radius:.6rem; padding:.7rem 1rem; font-weight:750; cursor:pointer; }.button.primary { color:#fff; background:#1d4ed8; }.button.ghost { color:#1e3a8a; background:#dbeafe; }.button:disabled { opacity:.55; cursor:not-allowed; }',
    '.hint { margin-top:.75rem; color:#475569; font-size:.88rem; }.error { color:#991b1b; font-weight:700; }',
    '.filters { display:flex; gap:1rem; padding:1rem; margin-bottom:1rem; background:#fff; border:1px solid #cbd5e1; border-radius:.8rem; }',
    '.filters label { display:grid; gap:.35rem; color:#374151; font-weight:750; }.filters select { min-width:13rem; border:1px solid #64748b; border-radius:.45rem; padding:.6rem; color:#111827; background:#fff; }',
    '.table { background:#fff; border:1px solid #cbd5e1; border-radius:1rem; overflow:hidden; }',
    '.table-head,.table-row { display:grid; grid-template-columns:1.4fr 1.3fr .9fr 1.5fr .8fr 1.2fr 30px; gap:.9rem; align-items:center; padding:1rem 1.2rem; }',
    '.table-head { color:#374151; background:#f1f5f9; font-weight:800; font-size:.85rem; }.table-row { color:#172033; text-decoration:none; border-top:1px solid #e5e7eb; }.table-row:hover { background:#eff6ff; }',
    '.table-row strong,.table-row small { display:block; }.table-row small { color:#4b5563; margin-top:.25rem; }.accepted { color:#334155; font-size:.9rem; }.arrow { color:#1d4ed8; font-size:1.3rem; text-align:right; }',
    '.alert { padding:.9rem 1rem; color:#991b1b; background:#fee2e2; border:1px solid #fca5a5; border-radius:.7rem; margin-bottom:1rem; }.link-button { border:0; background:transparent; color:#991b1b; text-decoration:underline; cursor:pointer; }',
    '.empty-state,.loading { padding:2.5rem; text-align:center; color:#334155; background:#fff; border:1px dashed #64748b; border-radius:1rem; }.empty-state strong,.empty-state span { display:block; }.empty-state span { margin-top:.35rem; }',
    '@media(max-width:1000px){.table-head{display:none}.table-row{grid-template-columns:1fr 1fr; gap:.65rem}.filters{flex-direction:column}.create-form{flex-direction:column; align-items:stretch}}',
  ],
})
export class TendersComponent {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  products: Product[] = [];
  tenders: TenderSummary[] = [];
  loading = true;
  error = '';
  createError = '';
  creating = false;
  readonly numberTr = numberTr;
  readonly filters = this.fb.group({ productId: [null as number | null], status: [''] });
  readonly createForm = this.fb.group({ productId: [null as number | null], quantityTon: [null as number | null] });
  private readonly refresh$ = new Subject<void>();
  private hasLoaded = false;

  constructor() {
    this.filters.valueChanges.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => this.refresh$.next());
    merge(timer(0, 3000), this.refresh$)
      .pipe(
        switchMap(() => {
          if (!this.hasLoaded) this.loading = true;
          const value = this.filters.getRawValue();
          return forkJoin({
            products: this.api.products(),
            tenders: this.api.tenders(value.productId ?? undefined, value.status || undefined),
          }).pipe(
            catchError(() => {
              this.error = 'İhaleler yüklenemedi.';
              if (!this.hasLoaded) this.loading = false;
              return EMPTY;
            }),
          );
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((result) => {
        this.products = result.products.items;
        this.tenders = result.tenders.items;
        this.loading = false;
        this.hasLoaded = true;
        this.error = '';
      });
  }

  get selectedProduct(): Product | null {
    const id = this.createForm.getRawValue().productId;
    return this.products.find((product) => product.id === id) ?? null;
  }

  get hasActiveTender(): boolean {
    return (this.selectedProduct?.active_tenders.length ?? 0) > 0;
  }

  quantityKg(tender: TenderSummary): string {
    return numberTr(Number(tender.quantity_ton) * 1000, 0);
  }

  useSuggested(): void {
    const suggested = Number(this.selectedProduct?.suggested_quantity_ton ?? 0);
    if (suggested > 0) {
      this.createForm.patchValue({ quantityTon: Number(suggested.toFixed(3)) });
    }
  }

  createTender(): void {
    const { productId, quantityTon } = this.createForm.getRawValue();
    if (this.creating || !productId || !quantityTon || quantityTon <= 0) {
      this.createError = 'Ürün ve sıfırdan büyük bir miktar girin.';
      return;
    }
    this.creating = true;
    this.createError = '';
    this.api
      .createTender(productId, quantityTon)
      .pipe(finalize(() => (this.creating = false)))
      .subscribe({
        next: (tender) => {
          this.createForm.patchValue({ quantityTon: null });
          void this.router.navigate(['/tenders', tender.id]);
        },
        error: (error: unknown) => {
          this.createError = apiErrorMessage(error, 'İhale açılamadı.');
        },
      });
  }

  load(): void {
    this.loading = true;
    this.refresh$.next();
  }
}
