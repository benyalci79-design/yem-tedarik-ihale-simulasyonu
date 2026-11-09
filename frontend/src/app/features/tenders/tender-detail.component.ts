import { CommonModule } from '@angular/common';
import { Component, DestroyRef, inject } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { catchError, EMPTY, switchMap, timer } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ApiService } from '../../core/api.service';
import { TenderDetail } from '../../core/models';
import { numberTr } from '../../shared/display';
import { StatusBadgeComponent } from '../../shared/status-badge.component';

@Component({
  selector: 'app-tender-detail',
  standalone: true,
  imports: [CommonModule, RouterLink, StatusBadgeComponent],
  template: `<a routerLink="/tenders" class="back-link">← İhale listesine dön</a><div *ngIf="error" class="alert">{{ error }}</div><ng-container *ngIf="tender as item"><section class="page-heading"><div><p class="eyebrow">{{ item.code }}</p><h1>{{ item.product_name }} ihalesi</h1><p class="lede">{{ numberTr(item.quantity_ton, 3) }} ton · {{ item.offer_count }}/{{ item.invited_count }} teklif</p></div><app-status-badge [status]="item.status"></app-status-badge></section><div class="detail-grid"><section class="detail-card"><h2>İhale akışı</h2><dl><div><dt>Açılış</dt><dd>{{ numberTr(item.opened_at_seconds, 1) }} sn</dd></div><div><dt>Teklif kapanışı</dt><dd>{{ numberTr(item.offer_closes_at_seconds, 1) }} sn</dd></div><div><dt>Değerlendirme</dt><dd>{{ numberTr(item.evaluate_at_seconds, 1) }} sn</dd></div><div><dt>Kalan süre</dt><dd>{{ numberTr(item.remaining_seconds, 1) }} sn</dd></div></dl><p *ngIf="item.status === 'OPEN'" class="privacy-note">🔒 Teklifler değerlendirmeye kadar gizli. Bu aşamada fiyat ve teslim ayrıntısı API’den gönderilmez.</p><p *ngIf="item.result_reason" class="reason">{{ item.result_reason }}</p></section><section class="detail-card"><h2>Teslim durumu</h2><div class="delivery-state"><strong>{{ item.delivery_status ?? 'Değerlendirme bekleniyor' }}</strong><span *ngIf="item.delivery_due_at_seconds">Beklenen an: {{ numberTr(item.delivery_due_at_seconds, 1) }} sn</span><span *ngIf="item.delivered_at_seconds">Gerçekleşen an: {{ numberTr(item.delivered_at_seconds, 1) }} sn</span></div><div class="offer-list" *ngIf="item.status !== 'OPEN'"><div class="offer-row offer-head"><span>NPC</span><span>Teklif</span><span>Karar</span><span></span></div><div class="offer-row" *ngFor="let offer of item.offers"><div><strong>{{ offer.npc_name }}</strong><small>{{ offer.offer_status }}</small></div><span *ngIf="offer.unit_price">{{ numberTr(offer.unit_price, 2) }} TL/ton<br><small>{{ numberTr(offer.total_amount ?? '0', 2) }} TL toplam</small></span><span *ngIf="!offer.unit_price" class="muted">Teklif yok</span><span>{{ offer.decision ?? '—' }}<small>{{ offer.decision_reason }}</small></span><span *ngIf="offer.delivery_minutes">{{ offer.delivery_minutes }} dk</span></div></div><div *ngIf="item.status === 'OPEN'" class="invite-list"><span *ngFor="let offer of item.offers" class="invite-chip">{{ offer.npc_name }} · davetli</span></div></section></div></ng-container><div *ngIf="!tender && !loading" class="empty-state">İhale bulunamadı.</div><div *ngIf="loading" class="loading">İhale detayı yükleniyor…</div>`,
  styles: ['.back-link { display:inline-block; margin-bottom:1.5rem; color:#1d4ed8; font-weight:750; text-decoration:none; }.page-heading { display:flex; justify-content:space-between; align-items:flex-end; gap:1rem; margin-bottom:2rem; }.eyebrow { color:#1d4ed8; font-size:.78rem; font-weight:800; letter-spacing:.08em; }.page-heading h1 { margin:.3rem 0; color:#111827; font-size:2.4rem; }.lede { color:#4b5563; }.detail-grid { display:grid; grid-template-columns:1fr 1.5fr; gap:1rem; }.detail-card { padding:1.25rem; background:#fff; border:1px solid #cbd5e1; border-radius:1rem; }.detail-card h2 { margin-top:0; color:#111827; }.detail-card dl { display:grid; gap:.8rem; }.detail-card dl div { display:flex; justify-content:space-between; border-bottom:1px solid #e5e7eb; padding-bottom:.6rem; }.detail-card dt { color:#4b5563; }.detail-card dd { margin:0; color:#111827; font-weight:800; }.privacy-note { padding:.85rem; color:#1e3a8a; background:#dbeafe; border-radius:.6rem; font-weight:700; line-height:1.45; }.reason { color:#374151; }.delivery-state { display:grid; gap:.45rem; padding:1rem; color:#166534; background:#dcfce7; border-radius:.7rem; }.delivery-state strong { font-size:1.2rem; }.offer-list { margin-top:1.25rem; }.offer-row { display:grid; grid-template-columns:1.3fr 1.2fr 1.6fr .6fr; gap:.75rem; align-items:center; padding:.85rem 0; border-bottom:1px solid #e5e7eb; }.offer-head { color:#374151; font-size:.8rem; font-weight:800; }.offer-row strong,.offer-row small { display:block; }.offer-row small { color:#4b5563; margin-top:.25rem; }.muted { color:#4b5563; }.invite-list { display:flex; flex-wrap:wrap; gap:.55rem; margin-top:1.25rem; }.invite-chip { color:#1e3a8a; background:#dbeafe; border-radius:999px; padding:.5rem .7rem; font-weight:700; }.alert { padding:.9rem 1rem; color:#991b1b; background:#fee2e2; border:1px solid #fca5a5; border-radius:.7rem; }.empty-state,.loading { padding:2.5rem; color:#334155; text-align:center; background:#fff; border:1px dashed #64748b; border-radius:1rem; } @media(max-width:850px){.detail-grid{grid-template-columns:1fr}.page-heading{align-items:flex-start; flex-direction:column}.offer-row{grid-template-columns:1fr 1fr}}']
})
export class TenderDetailComponent {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  tender: TenderDetail | null = null;
  loading = true;
  error = '';
  readonly numberTr = numberTr;

  constructor() {
    this.route.paramMap.pipe(
      switchMap(params => timer(0, 2000).pipe(switchMap(() => this.api.tender(Number(params.get('id')))))),
      catchError(() => { this.error = 'İhale detayı alınamadı.'; this.loading = false; return EMPTY; }),
      takeUntilDestroyed(this.destroyRef)
    ).subscribe(result => { this.tender = result; this.loading = false; });
  }
}
