import { CommonModule } from '@angular/common';
import { Component, DestroyRef, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { catchError, EMPTY, finalize, forkJoin, switchMap, timer } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ApiService, apiErrorMessage } from '../../core/api.service';
import { Carrier, Shipment, SimulationState } from '../../core/models';
import { awardStatusLabel, numberTr, simDurationShort } from '../../shared/display';
import { ToastService } from '../../shared/toast.service';

@Component({
  selector: 'app-shipping',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="page-heading">
      <div><p class="eyebrow">LOJİSTİK</p><h1>Nakliye</h1><p class="lede">Nakliye hariç teklifler için nakliyeci atayın; teslim süresi ve maliyet buna göre hesaplanır.</p></div>
    </section>

    <div *ngIf="error" class="alert">{{ error }} <button class="link-button" (click)="reload()">Yeniden dene</button></div>

    <section class="card">
      <div class="card-head"><h2>Nakliyeci bekleyenler</h2><span class="muted">{{ awaiting.length }} teslimat</span></div>
      <p class="hint" *ngIf="!awaiting.length && !loading">Şu an nakliyeci bekleyen teslimat yok. Nakliye hariç bir teklifi kabul ettiğinizde burada görünür.</p>
      <div class="table" *ngIf="awaiting.length">
        <div class="row head"><span>Ürün / NPC</span><span>Miktar</span><span>Nakliyeci</span><span>Önizleme</span><span></span></div>
        <div class="row" *ngFor="let shipment of awaiting">
          <div><strong>{{ shipment.product_name }}</strong><small>{{ shipment.npc_name }} · {{ shipment.tender_code }}</small></div>
          <span>{{ numberTr(shipment.quantity_kg, 0) }} kg</span>
          <select [(ngModel)]="selected[shipment.award_id]" [ngModelOptions]="{ standalone: true }" aria-label="Nakliyeci seçimi">
            <option [ngValue]="null">Nakliyeci seçin</option>
            <option *ngFor="let carrier of carriers" [ngValue]="carrier.id">
              {{ carrier.name }} · {{ numberTr(carrier.price_per_ton, 0) }} TL/ton · {{ numberTr(carrier.price_per_kg, 2) }} TL/kg · {{ carrier.transit_minutes }} dk
            </option>
          </select>
          <div class="preview" *ngIf="selected[shipment.award_id]">
            <strong>{{ numberTr(previewCost(shipment), 0) }} TL</strong>
            <small>tahmini teslim ≈ {{ simDurationShort(previewDue(shipment)) }}</small>
          </div>
          <span *ngIf="!selected[shipment.award_id]" class="muted">—</span>
          <button type="button" class="button" [disabled]="!selected[shipment.award_id] || pending[shipment.award_id]" (click)="assign(shipment)">Nakliyeciyi ata</button>
          <span class="row-error" *ngIf="rowError[shipment.award_id]">{{ rowError[shipment.award_id] }}</span>
        </div>
      </div>
    </section>

    <section class="card">
      <div class="card-head"><h2>Yoldakiler ve teslim edilenler</h2><span class="muted">{{ moving.length + delivered.length }} kayıt</span></div>
      <p class="hint" *ngIf="!moving.length && !delivered.length && !loading">Henüz yolda veya teslim edilmiş bir award yok.</p>
      <div class="table" *ngIf="moving.length || delivered.length">
        <div class="row head shipment"><span>Ürün / NPC</span><span>Miktar</span><span>Durum</span><span>Nakliyeci</span><span>Zaman</span><span>Maliyet</span></div>
        <div class="row shipment" *ngFor="let shipment of moving.concat(delivered)">
          <div><strong>{{ shipment.product_name }}</strong><small>{{ shipment.npc_name }} · {{ shipment.tender_code }}</small></div>
          <span>{{ numberTr(shipment.quantity_kg, 0) }} kg</span>
          <span class="status {{ shipment.status.toLowerCase() }}">{{ awardStatusLabel(shipment.status) }}</span>
          <span>{{ shipment.carrier_name ?? 'Nakliye dahil' }}</span>
          <span>
            <ng-container *ngIf="shipment.status === 'IN_TRANSIT'">{{ simDurationShort(shipment.remaining_seconds ?? 0) }} kaldı</ng-container>
            <ng-container *ngIf="shipment.status === 'DELIVERED'">{{ simDurationShort(shipment.delivered_at_seconds ?? 0) }} teslim</ng-container>
          </span>
          <strong>{{ shipment.landed_cost_tl ? (numberTr(shipment.landed_cost_tl, 0) + ' TL') : '—' }}</strong>
        </div>
      </div>
    </section>

    <section class="card carriers">
      <div class="card-head"><h2>Nakliyeciler</h2><span class="muted">{{ carriers.length }} firma</span></div>
      <div class="carrier-grid">
        <article *ngFor="let carrier of carriers">
          <strong>{{ carrier.name }}</strong>
          <span>{{ numberTr(carrier.price_per_ton, 0) }} TL/ton · {{ numberTr(carrier.price_per_kg, 2) }} TL/kg</span>
          <small>Taşıma süresi: {{ carrier.transit_minutes }} dk</small>
        </article>
      </div>
    </section>
  `,
  styles: [
    '.page-heading { margin-bottom:1.5rem; }.eyebrow { color:#1d4ed8; font-size:.78rem; font-weight:800; letter-spacing:.08em; }.page-heading h1 { margin:.3rem 0; color:#111827; font-size:2.4rem; }.lede { color:#4b5563; }',
    '.card { background:#fff; border:1px solid #cbd5e1; border-radius:1rem; padding:1.2rem; margin-bottom:1.2rem; }',
    '.card-head { display:flex; justify-content:space-between; align-items:center; gap:1rem; margin-bottom:.7rem; }.card-head h2 { margin:0; color:#111827; }',
    '.hint { color:#475569; font-size:.9rem; }.muted { color:#64748b; font-size:.85rem; }',
    '.table { display:grid; gap:.15rem; }.row { display:grid; grid-template-columns:1.5fr .8fr 1.6fr 1.1fr 1.1fr; gap:.8rem; align-items:center; padding:.75rem .5rem; border-bottom:1px solid #e5e7eb; }',
    '.row.head { grid-template-columns:1.5fr .8fr 1.6fr 1.1fr 1.1fr; color:#374151; font-size:.8rem; font-weight:800; background:#f1f5f9; border-radius:.4rem; }',
    '.row.shipment, .row.head.shipment { grid-template-columns:1.5fr .8fr 1fr 1.2fr 1.2fr 1fr; }',
    '.row small { display:block; color:#64748b; margin-top:.15rem; }',
    'select { width:100%; border:1px solid #64748b; border-radius:.5rem; padding:.5rem; background:#fff; color:#111827; }',
    '.preview { display:grid; gap:.1rem; }.preview small { color:#475569; }',
    '.button { border:0; border-radius:.55rem; padding:.6rem .8rem; color:#fff; background:#1d4ed8; font-weight:750; cursor:pointer; }.button:disabled { opacity:.5; cursor:not-allowed; }',
    '.status { font-weight:750; }.status.in_transit { color:#1d4ed8; }.status.delivered { color:#047857; }.status.awaiting_carrier { color:#b45309; }',
    '.row-error { grid-column:1/-1; color:#991b1b; font-size:.82rem; }',
    '.carrier-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.8rem; }.carrier-grid article { display:grid; gap:.2rem; padding:.9rem 1rem; background:#eff6ff; border:1px solid #bfdbfe; border-radius:.8rem; }.carrier-grid span { color:#1e3a8a; font-weight:700; font-size:.9rem; }.carrier-grid small { color:#475569; }',
    '.alert { padding:.9rem 1rem; color:#991b1b; background:#fee2e2; border:1px solid #fca5a5; border-radius:.7rem; margin-bottom:1rem; }.link-button { border:0; background:transparent; color:#991b1b; text-decoration:underline; cursor:pointer; }',
    '@media(max-width:1000px){.row,.row.head{grid-template-columns:1fr 1fr}.carrier-grid{grid-template-columns:1fr 1fr}.row.head{display:none}}',
  ],
})
export class ShippingComponent {
  private readonly api = inject(ApiService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly toast = inject(ToastService);
  simulation: SimulationState | null = null;
  carriers: Carrier[] = [];
  shipments: Shipment[] = [];
  selected: Record<number, number | null> = {};
  pending: Record<number, boolean> = {};
  rowError: Record<number, string> = {};
  loading = true;
  error = '';
  readonly numberTr = numberTr;
  readonly simDurationShort = simDurationShort;
  readonly awardStatusLabel = awardStatusLabel;

  constructor() {
    timer(0, 3000)
      .pipe(
        switchMap(() =>
          forkJoin({
            simulation: this.api.simulation(),
            carriers: this.api.carriers(),
            shipments: this.api.shipments(),
          }).pipe(
            catchError(() => {
              this.error = 'Nakliye verileri yüklenemedi.';
              this.loading = false;
              return EMPTY;
            }),
          ),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((result) => {
        this.simulation = result.simulation;
        this.carriers = result.carriers.items;
        this.shipments = result.shipments.items;
        for (const shipment of this.shipments) {
          if (this.selected[shipment.award_id] === undefined) {
            this.selected[shipment.award_id] = null;
          }
        }
        this.loading = false;
        this.error = '';
      });
  }

  get awaiting(): Shipment[] {
    return this.shipments.filter((shipment) => shipment.status === 'AWAITING_CARRIER');
  }

  get moving(): Shipment[] {
    return this.shipments.filter((shipment) => shipment.status === 'IN_TRANSIT');
  }

  get delivered(): Shipment[] {
    return this.shipments.filter((shipment) => shipment.status === 'DELIVERED');
  }

  carrierById(id: number | null): Carrier | null {
    return this.carriers.find((carrier) => carrier.id === id) ?? null;
  }

  previewCost(shipment: Shipment): number {
    const carrier = this.carrierById(this.selected[shipment.award_id] ?? null);
    if (!carrier) return 0;
    return (Number(shipment.quantity_kg) / 1000) * (Number(shipment.unit_price_per_ton) + Number(carrier.price_per_ton));
  }

  previewDue(shipment: Shipment): number {
    const carrier = this.carrierById(this.selected[shipment.award_id] ?? null);
    if (!carrier) return 0;
    const now = Number(this.simulation?.elapsed_seconds ?? 0);
    const ready = Number(shipment.accepted_at_seconds) + Number(shipment.delivery_minutes) * 60;
    return Math.max(ready, now) + carrier.transit_minutes * 60;
  }

  assign(shipment: Shipment): void {
    const carrierId = this.selected[shipment.award_id];
    if (!carrierId || this.pending[shipment.award_id]) return;
    this.pending[shipment.award_id] = true;
    this.rowError[shipment.award_id] = '';
    this.api
      .assignCarrier(shipment.award_id, carrierId)
      .pipe(finalize(() => (this.pending[shipment.award_id] = false)))
      .subscribe({
        next: () => {
          this.toast.show('Nakliyeci atandı, teslimat yola çıktı');
          delete this.selected[shipment.award_id];
          this.reload();
        },
        error: (error: unknown) => {
          this.rowError[shipment.award_id] = apiErrorMessage(error, 'Nakliyeci atanamadı.');
        },
      });
  }

  reload(): void {
    forkJoin({ carriers: this.api.carriers(), shipments: this.api.shipments() }).subscribe({
      next: (result) => {
        this.carriers = result.carriers.items;
        this.shipments = result.shipments.items;
        this.error = '';
      },
      error: () => (this.error = 'Nakliye verileri yüklenemedi.'),
    });
  }
}
