import { CommonModule } from '@angular/common';
import { Component, DestroyRef, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { catchError, EMPTY, finalize } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ApiService, apiErrorMessage } from '../../core/api.service';
import { Product } from '../../core/models';
import { numberTr } from '../../shared/display';

@Component({
  selector: 'app-products',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  template: `
    <section class="page-heading">
      <div><p class="eyebrow">AYARLAR</p><h1>Ürün ayarları</h1><p class="lede">Stok, depo kapasitesi ve ortalama maliyeti yönetin.</p></div>
      <span class="info-chip">Değişiklik için simülasyonu duraklatın</span>
    </section>
    <div *ngIf="error" class="alert">{{ error }} <button class="link-button" (click)="load()">Yeniden dene</button></div>
    <div *ngIf="loading && !products.length" class="loading">Ürün ayarları hazırlanıyor…</div>

    <div class="product-settings" *ngIf="products.length || !loading">
      <article class="settings-card" *ngFor="let product of products">
        <div class="card-title">
          <div><span class="code-label">{{ product.code }}</span><h2>{{ product.name }}</h2></div>
          <span class="lock-note" *ngIf="product.active_tenders.length">🔒 Aktif süreç var</span>
        </div>

        <div class="occupancy">
          <div class="bar"><span [style.width.%]="fillPercent(product)"></span></div>
          <small>
            Doluluk: {{ numberTr(product.current_stock_kg, 0) }} / {{ numberTr(product.capacity_kg, 0) }} kg (%{{ numberTr(fillPercent(product), 0) }})
            · Yolda {{ numberTr(product.incoming_kg, 0) }} kg · Değer {{ numberTr(product.stock_value_tl, 0) }} TL
          </small>
        </div>

        <form [formGroup]="forms[product.id]" (ngSubmit)="save(product)">
          <div class="form-grid">
            <label>Mevcut stok (kg)<input type="number" formControlName="current_stock_kg" min="0" step="0.001"></label>
            <label>Tüketim (kg/dk)<input type="number" formControlName="consumption_kg_per_min" min="0.001" step="0.001"></label>
            <label>Kritik kapsama (dk)<input type="number" formControlName="critical_coverage_minutes" min="0.01" step="0.01"></label>
            <label>Hedef kapsama (dk)<input type="number" formControlName="target_coverage_minutes" min="0.01" step="0.01"></label>
            <label>Teklif penceresi (sn)<input type="number" formControlName="offer_window_seconds" min="10" max="600" step="1"></label>
            <label>Depo kapasitesi (kg)<input type="number" formControlName="capacity_kg" min="1" step="0.001"></label>
            <label>Ortalama maliyet (TL/kg)<input type="number" formControlName="avg_cost_per_kg" min="0" step="0.000001"></label>
          </div>
          <div class="current-values">
            <span>Kapsama: <strong>{{ numberTr(product.coverage_minutes, 1) }} dk</strong></span>
            <span>Önerilen ihale: <strong>{{ numberTr(product.suggested_quantity_ton, 3) }} ton</strong></span>
            <span>Son alım: <strong>{{ numberTr(product.last_purchase_unit_price, 2) }} TL/kg</strong></span>
          </div>
          <div class="form-actions">
            <span class="form-error" *ngIf="formError[product.id]">{{ formError[product.id] }}</span>
            <button class="button button-primary" type="submit" [disabled]="forms[product.id].invalid || saving[product.id]">Kaydet</button>
          </div>
        </form>
      </article>
    </div>
    <div class="empty-state" *ngIf="!loading && !products.length">Ürün bulunamadı.</div>
  `,
  styles: [
    '.page-heading,.card-title,.form-actions,.current-values { display:flex; align-items:center; justify-content:space-between; gap:1rem; }',
    '.page-heading { margin-bottom:2rem; }.eyebrow,.code-label { color:#1d4ed8; font-size:.78rem; font-weight:800; letter-spacing:.08em; }.page-heading h1 { margin:.3rem 0; color:#111827; font-size:2.4rem; }.lede { color:#4b5563; }',
    '.info-chip,.lock-note { color:#1e3a8a; background:#dbeafe; padding:.55rem .75rem; border-radius:999px; font-weight:750; }',
    '.product-settings { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:1rem; }.settings-card { background:#fff; border:1px solid #cbd5e1; border-radius:1rem; padding:1.25rem; }',
    '.card-title { align-items:flex-start; margin-bottom:.8rem; }.card-title h2 { margin:.25rem 0 0; color:#111827; }',
    '.occupancy { display:grid; gap:.35rem; margin-bottom:1.1rem; }.bar { height:.55rem; background:#e2e8f0; border-radius:999px; overflow:hidden; }.bar span { display:block; height:100%; background:linear-gradient(90deg,#2563eb,#1d4ed8); }.occupancy small { color:#475569; }',
    '.form-grid { display:grid; grid-template-columns:repeat(2,1fr); gap:1rem; }.form-grid label { display:grid; gap:.35rem; color:#374151; font-size:.9rem; font-weight:700; }.form-grid input { width:100%; border:1px solid #64748b; border-radius:.5rem; padding:.65rem; color:#111827; background:#fff; }.form-grid input:focus { outline:3px solid #bfdbfe; border-color:#1d4ed8; }',
    '.current-values { justify-content:flex-start; gap:1.5rem; margin:1.2rem 0; color:#4b5563; font-size:.9rem; }.current-values strong { color:#111827; font-size:1.05rem; }',
    '.form-actions { border-top:1px solid #e5e7eb; padding-top:1rem; }.button { border:0; border-radius:.6rem; padding:.7rem 1rem; color:#fff; background:#1d4ed8; font-weight:750; cursor:pointer; }.button:disabled { opacity:.55; cursor:not-allowed; }.form-error,.alert-error { color:#991b1b; }',
    '.alert { padding:.9rem 1rem; border-radius:.7rem; background:#fee2e2; border:1px solid #fca5a5; margin-bottom:1rem; }.link-button { border:0; background:transparent; color:#991b1b; text-decoration:underline; cursor:pointer; }.loading { padding:2rem; color:#374151; }.empty-state { padding:2rem; text-align:center; background:#fff; border:1px dashed #64748b; color:#334155; }',
    '@media(max-width:1000px){.product-settings{grid-template-columns:1fr}.page-heading{align-items:flex-start; flex-direction:column}}',
  ],
})
export class ProductsComponent {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  private readonly destroyRef = inject(DestroyRef);
  products: Product[] = [];
  forms: Record<number, ReturnType<FormBuilder['group']>> = {};
  saving: Record<number, boolean> = {};
  formError: Record<number, string> = {};
  loading = true;
  error = '';
  readonly numberTr = numberTr;

  constructor() {
    this.load();
  }

  load(): void {
    this.error = '';
    this.api
      .products()
      .pipe(
        catchError(() => {
          this.error = 'Ürünler yüklenemedi.';
          this.loading = false;
          return EMPTY;
        }),
        finalize(() => (this.loading = false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((result) => {
        this.products = result.items;
        this.error = '';
        for (const product of this.products) {
          this.forms[product.id] = this.fb.group({
            current_stock_kg: [Number(Number(product.current_stock_kg).toFixed(3)), [Validators.required, Validators.min(0)]],
            consumption_kg_per_min: [Number(product.consumption_kg_per_min), [Validators.required, Validators.min(.001)]],
            critical_coverage_minutes: [Number(product.critical_coverage_minutes), [Validators.required, Validators.min(.01)]],
            target_coverage_minutes: [Number(product.target_coverage_minutes), [Validators.required, Validators.min(.01)]],
            offer_window_seconds: [product.offer_window_seconds, [Validators.required, Validators.min(10), Validators.max(600)]],
            capacity_kg: [Number(product.capacity_kg), [Validators.required, Validators.min(1)]],
            avg_cost_per_kg: [Number(product.avg_cost_per_kg), [Validators.required, Validators.min(0)]],
          });
        }
      });
  }

  fillPercent(product: Product): number {
    const capacity = Number(product.capacity_kg);
    if (!capacity) return 0;
    return Math.max(0, Math.min(100, ((Number(product.current_stock_kg) + Number(product.incoming_kg)) / capacity) * 100));
  }

  save(product: Product): void {
    const form = this.forms[product.id];
    if (form.invalid) return;
    const values = form.getRawValue() as Record<string, number>;
    if (Number(values['target_coverage_minutes']) <= Number(values['critical_coverage_minutes'])) {
      this.formError[product.id] = 'Hedef kapsama kritik kapsama değerinden büyük olmalıdır.';
      return;
    }
    if (Number(values['capacity_kg']) < Number(values['current_stock_kg'])) {
      this.formError[product.id] = 'Depo kapasitesi mevcut stoktan küçük olamaz.';
      return;
    }
    this.saving[product.id] = true;
    this.formError[product.id] = '';
    this.api
      .updateProduct(product.id, values as unknown as Partial<Product>)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.saving[product.id] = false;
          this.load();
        },
        error: (error: unknown) => {
          this.saving[product.id] = false;
          this.formError[product.id] = apiErrorMessage(error, 'Ayar kaydedilemedi.');
        },
      });
  }
}
