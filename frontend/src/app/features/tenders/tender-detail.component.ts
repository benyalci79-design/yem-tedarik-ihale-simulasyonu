import { CommonModule } from '@angular/common';
import { Component, DestroyRef, inject } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { catchError, EMPTY, finalize, switchMap, timer } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ApiService, apiErrorMessage } from '../../core/api.service';
import { TenderDetail, TenderOffer } from '../../core/models';
import { awardStatusLabel, decisionLabel, numberTr } from '../../shared/display';
import { StatusBadgeComponent } from '../../shared/status-badge.component';

@Component({
  selector: 'app-tender-detail',
  standalone: true,
  imports: [CommonModule, RouterLink, StatusBadgeComponent],
  template: `
    <a routerLink="/tenders" class="back-link">← İhale listesine dön</a>
    <div *ngIf="error" class="alert">{{ error }} <button class="link-button" (click)="reload()">Yeniden dene</button></div>

    <ng-container *ngIf="tender as item">
      <section class="page-heading">
        <div>
          <p class="eyebrow">{{ item.code }} · {{ item.product_name }}</p>
          <h1>{{ numberTr(item.quantity_ton, 3) }} tonluk ihale</h1>
          <p class="lede">{{ item.offer_count }}/{{ item.invited_count }} NPC teklif verdi<ng-container *ngIf="item.status === 'OPEN'"> · {{ numberTr(item.remaining_seconds, 0) }} sn kaldı</ng-container></p>
        </div>
        <app-status-badge [status]="item.status"></app-status-badge>
      </section>

      <section class="stock-strip" aria-label="Ürün stok ve maliyet özeti">
        <span class="strip-title">Depo</span>
        <span><b>{{ numberTr(item.product_stock_kg, 0) }}</b> / {{ numberTr(item.product_capacity_kg, 0) }} kg</span>
        <span class="sep">·</span>
        <span>Yolda <b>{{ numberTr(incomingKg(item), 0) }}</b> kg</span>
        <span class="sep">·</span>
        <span>Boş <b>{{ numberTr(item.free_capacity_kg, 0) }}</b> kg</span>
        <span class="sep">·</span>
        <span class="buy">Son alım <b>{{ numberTr(item.product_last_purchase_unit_price, 2) }} TL/kg</b></span>
        <span class="sep">·</span>
        <span>Ortalama <b>{{ numberTr(item.product_avg_cost_per_kg, 2) }} TL/kg</b></span>
      </section>

      <section class="need-grid">
        <article><span>İhtiyaç</span><strong>{{ numberTr(item.quantity_ton, 3) }} ton</strong></article>
        <article><span>Kabul edilen</span><strong>{{ numberTr(item.accepted_total_kg, 0) }} kg</strong></article>
        <article [class.done]="Number(item.remaining_need_kg) === 0"><span>Kalan ihtiyaç</span><strong>{{ numberTr(item.remaining_need_kg, 0) }} kg</strong></article>
        <article><span>Boş kapasite</span><strong>{{ numberTr(item.free_capacity_kg, 0) }} kg</strong></article>
      </section>

      <p *ngIf="item.result_reason" class="reason">{{ item.result_reason }}</p>

      <section class="card" *ngIf="item.status === 'OPEN'">
        <div class="card-head"><h2>Teklifler gizli</h2><span class="live">Teklif süresi işliyor</span></div>
        <p class="privacy">🔒 Süre dolana kadar tekliflerin fiyatı, miktarı ve nakliye modu API'den gönderilmez.</p>
        <div class="invite-list"><span *ngFor="let offer of item.offers" class="invite-chip">{{ offer.npc_name }} · davetli</span></div>
      </section>

      <section class="card" *ngIf="item.status === 'EVALUATION'">
        <div class="card-head">
          <h2>Teklifleri değerlendir</h2>
          <button type="button" class="button finalize" [disabled]="finalizing" (click)="finalize()">İhaleyi tamamla</button>
        </div>
        <p class="hint">Bir ihaleyi birden çok NPC'den karşılayabilirsiniz. Bir tekliften yalnızca bir kez miktar alınır; kalanı kısmi kabul olarak işaretlenir.</p>
        <p class="trend-legend" *ngIf="lastPurchase() > 0">
          Son alım <b>{{ numberTr(lastPurchase(), 2) }} TL/kg</b> ·
          <span class="trend up">▲</span> son alımdan ucuz ·
          <span class="trend down">▼</span> son alımdan pahalı
        </p>
        <p class="error" *ngIf="finalizeError">{{ finalizeError }}</p>

        <div class="offer-table">
          <div class="offer-row offer-head">
            <span>NPC</span><span>Fiyat</span><span>Teklif</span><span>Teslim</span><span>Nakliye</span><span>Karar</span><span>Kabul miktarı</span><span></span>
          </div>
          <div class="offer-row" *ngFor="let offer of item.offers" [class.muted-row]="offer.offer_status !== 'Teklif verdi'">
            <div class="npc"><strong>{{ offer.npc_name }}</strong><small>{{ offer.offer_status }}</small></div>
            <div class="price" *ngIf="offer.unit_price">
              <strong>{{ numberTr(offer.unit_price, 0) }} TL/ton</strong>
              <small>
                {{ numberTr(offer.unit_price_per_kg ?? 0, 2) }} TL/kg
                <span class="trend up" *ngIf="isCheaper(offer)" title="Son alım fiyatından ucuz">▲</span>
                <span class="trend down" *ngIf="isPricier(offer)" title="Son alım fiyatından pahalı">▼</span>
              </small>
            </div>
            <span *ngIf="!offer.unit_price" class="muted">—</span>
            <span>{{ offer.offered_quantity_kg ? (numberTr(offer.offered_quantity_kg, 0) + ' kg') : '—' }}</span>
            <span>{{ offer.delivery_minutes ? (offer.delivery_minutes + ' dk') : '—' }}</span>
            <span class="freight" [class.excluded]="offer.freight_included === false">{{ offer.freight_included === undefined ? '—' : (offer.freight_included ? 'Dahil' : 'Hariç') }}</span>
            <span class="decision" [class.accepted]="offer.decision === 'ACCEPTED'" [class.partial]="offer.decision === 'PARTIAL'" [class.rejected]="offer.decision === 'REJECTED'" [class.pending]="!offer.decision || offer.decision === 'PENDING'">{{ decisionLabel(offer.decision) }}</span>
            <div class="accept-box" *ngIf="canAccept(offer)">
              <input
                type="number"
                [value]="acceptQty[offer.participation_id]"
                [max]="offer.max_acceptable_kg"
                min="0.001"
                step="0.001"
                (input)="onQtyInput(offer.participation_id, $event)"
                aria-label="Kabul edilecek miktar (kg)"
              >
              <small>en fazla {{ numberTr(offer.max_acceptable_kg ?? 0, 0) }} kg</small>
            </div>
            <span *ngIf="!canAccept(offer)" class="muted">{{ offer.accepted_quantity_kg && Number(offer.accepted_quantity_kg) > 0 ? (numberTr(offer.accepted_quantity_kg, 0) + ' kg') : '—' }}</span>
            <button type="button" class="button accept" *ngIf="canAccept(offer)" [disabled]="accepting[offer.participation_id]" (click)="accept(offer)">Kabul et</button>
            <span *ngIf="!canAccept(offer)"></span>
            <span class="row-error" *ngIf="rowError[offer.participation_id]">{{ rowError[offer.participation_id] }}</span>
          </div>
        </div>
      </section>

      <section class="card" *ngIf="item.awards.length">
        <div class="card-head"><h2>Teslimatlar</h2><span class="muted">{{ item.awards.length }} award</span></div>
        <div class="award-table">
          <div class="award-row award-head"><span>NPC</span><span>Miktar</span><span>Fiyat</span><span>Nakliye</span><span>Durum</span><span>Teslim</span><span>Toplam maliyet</span></div>
          <div class="award-row" *ngFor="let award of item.awards">
            <strong>{{ award.npc_name }}</strong>
            <span>{{ numberTr(award.quantity_kg, 0) }} kg</span>
            <span>{{ numberTr(award.unit_price_per_ton, 0) }} TL/ton<small>{{ numberTr(award.unit_price_per_kg, 2) }} TL/kg</small></span>
            <span>
              <ng-container *ngIf="award.freight_included">Dahil</ng-container>
              <ng-container *ngIf="!award.freight_included">
                {{ award.carrier_name ?? 'Hariç' }}
                <small *ngIf="award.carrier_price_per_ton">{{ numberTr(award.carrier_price_per_ton, 0) }} TL/ton</small>
              </ng-container>
            </span>
            <span class="award-status {{ award.status.toLowerCase() }}">{{ awardStatusLabel(award.status) }}</span>
            <span>
              <ng-container *ngIf="award.delivered_at_seconds">{{ numberTr(award.delivered_at_seconds, 0) }} sn</ng-container>
              <ng-container *ngIf="!award.delivered_at_seconds && award.delivery_due_at_seconds">≈ {{ numberTr(award.delivery_due_at_seconds, 0) }} sn</ng-container>
              <ng-container *ngIf="!award.delivery_due_at_seconds">—</ng-container>
            </span>
            <strong>{{ award.landed_cost_tl ? (numberTr(award.landed_cost_tl, 0) + ' TL') : '—' }}</strong>
          </div>
        </div>
        <p class="hint" *ngIf="item.status === 'AWARDED'">Nakliye hariç teslimatlar için <a routerLink="/shipping" class="text-link">Nakliye</a> sekmesinden nakliyeci seçin.</p>
      </section>
    </ng-container>

    <div *ngIf="!tender && !loading" class="empty-state">İhale bulunamadı.</div>
    <div *ngIf="loading && !tender" class="loading">İhale detayı hazırlanıyor…</div>
  `,
  styles: [
    '.back-link { display:inline-block; margin-bottom:1.2rem; color:#1d4ed8; font-weight:750; text-decoration:none; }',
    '.page-heading { display:flex; justify-content:space-between; align-items:flex-end; gap:1rem; margin-bottom:1.5rem; }',
    '.eyebrow { color:#1d4ed8; font-size:.78rem; font-weight:800; letter-spacing:.08em; }.page-heading h1 { margin:.3rem 0; color:#111827; font-size:2.2rem; }.lede { color:#4b5563; }',
    '.need-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.8rem; margin-bottom:1.2rem; }',
    '.stock-strip { display:flex; flex-wrap:wrap; align-items:center; gap:.45rem; padding:.55rem .85rem; margin-bottom:.9rem; background:#f1f5f9; border:1px solid #e2e8f0; border-radius:.65rem; color:#334155; font-size:.85rem; }',
    '.stock-strip b { color:#111827; font-variant-numeric:tabular-nums; }.stock-strip .sep { color:#94a3b8; }.stock-strip .strip-title { font-weight:800; color:#1d4ed8; font-size:.75rem; letter-spacing:.06em; text-transform:uppercase; }.stock-strip .buy b { color:#1d4ed8; }',    '.need-grid article { display:grid; gap:.2rem; padding:.9rem 1rem; background:#eff6ff; border:1px solid #bfdbfe; border-radius:.8rem; }.need-grid span { color:#475569; font-size:.8rem; }.need-grid strong { color:#1e3a8a; font-size:1.3rem; }.need-grid article.done { background:#dcfce7; border-color:#86efac; }.need-grid article.done strong { color:#166534; }',
    '.reason { padding:.8rem 1rem; background:#f1f5f9; border-left:4px solid #1d4ed8; border-radius:.5rem; color:#172033; }',
    '.card { background:#fff; border:1px solid #cbd5e1; border-radius:1rem; padding:1.2rem; margin-bottom:1.2rem; }',
    '.card-head { display:flex; justify-content:space-between; align-items:center; gap:1rem; margin-bottom:.8rem; }.card-head h2 { margin:0; color:#111827; }.live { color:#047857; font-weight:800; font-size:.8rem; letter-spacing:.06em; }',
    '.privacy { padding:.85rem; color:#1e3a8a; background:#dbeafe; border-radius:.6rem; font-weight:700; }',
    '.invite-list { display:flex; flex-wrap:wrap; gap:.55rem; margin-top:1rem; }.invite-chip { color:#1e3a8a; background:#dbeafe; border-radius:999px; padding:.5rem .7rem; font-weight:700; }',
    '.button { border:0; border-radius:.6rem; padding:.7rem 1rem; font-weight:750; cursor:pointer; color:#fff; background:#1d4ed8; }.button:disabled { opacity:.55; cursor:not-allowed; }.button.finalize { background:#047857; }.button.accept { padding:.5rem .7rem; font-size:.85rem; }',
    '.hint { color:#475569; font-size:.88rem; }.error { color:#991b1b; font-weight:700; }',
    '.offer-table,.award-table { display:grid; gap:.2rem; margin-top:.6rem; }',
    '.offer-row { display:grid; grid-template-columns:1.4fr 1fr 1fr .7fr .7fr .9fr 1.4fr .9fr; gap:.7rem; align-items:center; padding:.7rem .5rem; border-bottom:1px solid #e5e7eb; }',
    '.offer-head,.award-head { color:#374151; font-size:.8rem; font-weight:800; background:#f1f5f9; border-radius:.4rem; }',
    '.offer-row small,.award-row small { display:block; color:#64748b; margin-top:.15rem; }',
    '.muted-row { opacity:.7; }.muted { color:#64748b; }.price strong { display:block; }.trend { font-size:.9em; font-weight:900; }.trend.up { color:#047857; }.trend.down { color:#b91c1c; }',
    '.trend-legend { margin:.1rem 0 .7rem; color:#475569; font-size:.82rem; }.trend-legend b { color:#111827; }',
    '.freight { font-weight:750; color:#047857; }.freight.excluded { color:#b45309; }',
    '.decision { font-weight:750; }.decision.accepted { color:#047857; }.decision.partial { color:#b45309; }.decision.rejected { color:#991b1b; }.decision.pending { color:#475569; }',
    '.accept-box { display:grid; gap:.2rem; }.accept-box input { width:100%; border:1px solid #64748b; border-radius:.45rem; padding:.45rem; }.accept-box small { color:#64748b; font-size:.72rem; }',
    '.row-error { grid-column:1/-1; color:#991b1b; font-size:.82rem; }',
    '.award-row { display:grid; grid-template-columns:1.3fr .8fr 1.2fr 1.2fr 1fr .9fr .9fr; gap:.7rem; align-items:center; padding:.7rem .5rem; border-bottom:1px solid #e5e7eb; }',
    '.award-status { font-weight:750; }.award-status.awaiting_carrier { color:#b45309; }.award-status.in_transit { color:#1d4ed8; }.award-status.delivered { color:#047857; }',
    '.text-link { color:#1d4ed8; font-weight:750; text-decoration:none; }',
    '.alert { padding:.9rem 1rem; color:#991b1b; background:#fee2e2; border:1px solid #fca5a5; border-radius:.7rem; margin-bottom:1rem; }.link-button { border:0; background:transparent; color:#991b1b; text-decoration:underline; cursor:pointer; }',
    '.empty-state,.loading { padding:2.5rem; color:#334155; text-align:center; background:#fff; border:1px dashed #64748b; border-radius:1rem; }',
    '@media(max-width:1000px){.need-grid{grid-template-columns:1fr 1fr}.offer-row,.award-row{grid-template-columns:1fr 1fr}.offer-head,.award-head{display:none}.page-heading{align-items:flex-start; flex-direction:column}}',
  ],
})
export class TenderDetailComponent {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  tender: TenderDetail | null = null;
  loading = true;
  error = '';
  finalizeError = '';
  finalizing = false;
  acceptQty: Record<number, number> = {};
  rowError: Record<number, string> = {};
  accepting: Record<number, boolean> = {};
  private touched: Record<number, boolean> = {};
  readonly Number = Number;
  readonly numberTr = numberTr;
  readonly decisionLabel = decisionLabel;
  readonly awardStatusLabel = awardStatusLabel;

  constructor() {
    this.route.paramMap
      .pipe(
        switchMap((params) =>
          timer(0, 2000).pipe(
            switchMap(() => this.api.tender(Number(params.get('id')))),
            catchError(() => {
              this.error = 'İhale detayı alınamadı.';
              this.loading = false;
              return EMPTY;
            }),
          ),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((tender) => this.apply(tender));
  }

  lastPurchase(): number {
    return Number(this.tender?.product_last_purchase_unit_price ?? 0);
  }

  isCheaper(offer: TenderOffer): boolean {
    const price = Number(offer.unit_price_per_kg ?? 0);
    return this.lastPurchase() > 0 && price > 0 && price < this.lastPurchase();
  }

  isPricier(offer: TenderOffer): boolean {
    const price = Number(offer.unit_price_per_kg ?? 0);
    return this.lastPurchase() > 0 && price > this.lastPurchase();
  }

  incomingKg(tender: TenderDetail): number {
    return Math.max(
      0,
      Number(tender.product_capacity_kg) - Number(tender.product_stock_kg) - Number(tender.free_capacity_kg),
    );
  }

  canAccept(offer: TenderOffer): boolean {
    return (
      this.tender?.status === 'EVALUATION' &&
      offer.offer_status === 'Teklif verdi' &&
      offer.decision === 'PENDING' &&
      Number(offer.max_acceptable_kg ?? 0) > 0
    );
  }

  onQtyInput(participationId: number, event: Event): void {
    const input = event.target as HTMLInputElement;
    this.touched[participationId] = true;
    const value = Number(input.value);
    this.acceptQty[participationId] = Number.isFinite(value) ? value : 0;
  }

  accept(offer: TenderOffer): void {
    if (!this.tender || this.accepting[offer.participation_id]) return;
    const quantity = this.acceptQty[offer.participation_id] ?? 0;
    if (!quantity || quantity <= 0) {
      this.rowError[offer.participation_id] = 'Sıfırdan büyük bir miktar girin.';
      return;
    }
    this.accepting[offer.participation_id] = true;
    this.rowError[offer.participation_id] = '';
    this.api
      .acceptOffer(this.tender.id, offer.participation_id, quantity)
      .pipe(finalize(() => (this.accepting[offer.participation_id] = false)))
      .subscribe({
        next: (tender) => {
          this.touched[offer.participation_id] = false;
          delete this.acceptQty[offer.participation_id];
          this.apply(tender);
        },
        error: (error: unknown) => {
          this.rowError[offer.participation_id] = apiErrorMessage(error, 'Teklif kabul edilemedi.');
        },
      });
  }

  finalize(): void {
    if (!this.tender || this.finalizing) return;
    const remaining = Number(this.tender.remaining_need_kg);
    const message =
      this.tender.awards.length === 0
        ? 'Hiçbir teklif kabul edilmedi. İhale sonuçsuz olarak kapatılsın mı?'
        : remaining > 0
          ? `Kalan ${numberTr(remaining, 0)} kg alınmayacak. İhale tamamlansın mı?`
          : 'İhale tamamlansın mı?';
    if (!window.confirm(message)) return;
    this.finalizing = true;
    this.finalizeError = '';
    this.api
      .finalizeTender(this.tender.id)
      .pipe(finalize(() => (this.finalizing = false)))
      .subscribe({
        next: (tender) => this.apply(tender),
        error: (error: unknown) => {
          this.finalizeError = apiErrorMessage(error, 'İhale tamamlanamadı.');
        },
      });
  }

  reload(): void {
    this.loading = true;
    this.error = '';
    this.tender = null;
    const id = Number(this.route.snapshot.paramMap.get('id'));
    this.api
      .tender(id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (result) => this.apply(result),
        error: () => {
          this.error = 'İhale detayı alınamadı.';
          this.loading = false;
        },
      });
  }

  private apply(tender: TenderDetail): void {
    this.tender = tender;
    this.loading = false;
    this.error = '';
    for (const offer of tender.offers) {
      if (this.touched[offer.participation_id]) continue;
      this.acceptQty[offer.participation_id] = Number(offer.max_acceptable_kg ?? 0);
    }
  }
}
