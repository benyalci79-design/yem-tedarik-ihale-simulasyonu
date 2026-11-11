import { CommonModule } from '@angular/common';
import { Component, DestroyRef, inject } from '@angular/core';
import { catchError, EMPTY, switchMap, timer } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ApiService } from '../../core/api.service';
import { SupplierScore } from '../../core/models';
import { numberTr } from '../../shared/display';

@Component({
  selector: 'app-suppliers',
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="page-heading">
      <div><p class="eyebrow">TEDARİKÇİ YÖNETİMİ</p><h1>Tedarikçi skorları</h1><p class="lede">Geçmiş teklif ve teslimat verisinden otomatik hesaplanır.</p></div>
      <span class="formula">Skor = %50 fiyat rekabeti + %30 katılım + %20 kazanma</span>
    </section>

    <div *ngIf="error" class="alert">{{ error }} <button class="link-button" (click)="reload()">Yeniden dene</button></div>
    <div *ngIf="loading && !scores.length" class="loading">Tedarikçi skorları hazırlanıyor…</div>

    <div class="table" *ngIf="scores.length">
      <div class="row head"><span>#</span><span>Tedarikçi</span><span>Skor</span><span>Davet</span><span>Teklif</span><span>Kazanma</span><span>Katılım</span><span>Fiyat sapması</span><span>Ort. teslim</span></div>
      <div class="row" *ngFor="let item of scores; let index = index">
        <span class="rank" [class.top]="index < 3">{{ index + 1 }}</span>
        <div><strong>{{ item.name }}</strong><small>{{ item.code }}</small></div>
        <div class="score-cell">
          <strong>{{ numberTr(item.score, 0) }}</strong>
          <div class="score-bar"><span [style.width.%]="Number(item.score)"></span></div>
        </div>
        <span>{{ item.invitations }}</span>
        <span>{{ item.offers }}</span>
        <span>{{ item.awards }}</span>
        <span>{{ pct(item.response_rate) }}</span>
        <span [class.good]="Number(item.avg_price_deviation_pct) < 0" [class.bad]="Number(item.avg_price_deviation_pct) > 0">
          {{ Number(item.avg_price_deviation_pct) > 0 ? '+' : '' }}{{ numberTr(item.avg_price_deviation_pct, 1) }}%
        </span>
        <span>{{ numberTr(item.avg_delivery_minutes, 0) }} dk</span>
      </div>
    </div>

    <div class="empty-state" *ngIf="!loading && !scores.length">Tedarikçi verisi bulunamadı.</div>
  `,
  styles: [
    '.page-heading { display:flex; justify-content:space-between; align-items:flex-end; gap:1rem; margin-bottom:1.6rem; }.eyebrow { color:#1d4ed8; font-size:.78rem; font-weight:800; letter-spacing:.08em; }.page-heading h1 { margin:.3rem 0; color:#111827; font-size:2.4rem; }.lede { color:#4b5563; }',
    '.formula { color:#1e3a8a; background:#dbeafe; border-radius:999px; padding:.5rem .8rem; font-weight:700; font-size:.82rem; white-space:nowrap; }',
    '.table { background:#fff; border:1px solid #cbd5e1; border-radius:1rem; overflow:hidden; }',
    '.row { display:grid; grid-template-columns:40px 1.6fr 1.2fr .6fr .6fr .7fr .7fr .9fr .8fr; gap:.7rem; align-items:center; padding:.75rem 1rem; border-top:1px solid #e5e7eb; }',
    '.row.head { border-top:0; background:#f1f5f9; color:#374151; font-size:.78rem; font-weight:800; text-transform:uppercase; letter-spacing:.04em; }',
    '.row small { display:block; color:#64748b; margin-top:.1rem; }.rank { font-weight:800; color:#64748b; }.rank.top { color:#1d4ed8; }',
    '.score-cell { display:flex; align-items:center; gap:.5rem; }.score-cell strong { min-width:2rem; }.score-bar { flex:1; height:.5rem; background:#e2e8f0; border-radius:999px; overflow:hidden; }.score-bar span { display:block; height:100%; background:linear-gradient(90deg,#60a5fa,#1d4ed8); }',
    '.good { color:#047857; font-weight:750; }.bad { color:#b91c1c; font-weight:750; }',
    '.alert { padding:.9rem 1rem; color:#991b1b; background:#fee2e2; border:1px solid #fca5a5; border-radius:.7rem; margin-bottom:1rem; }.link-button { border:0; background:transparent; color:#991b1b; text-decoration:underline; cursor:pointer; }',
    '.loading,.empty-state { padding:2.5rem; text-align:center; color:#334155; background:#fff; border:1px dashed #64748b; border-radius:1rem; }',
    '@media(max-width:1000px){.row.head{display:none}.row{grid-template-columns:1fr 1fr; gap:.5rem}.formula{display:none}}',
  ],
})
export class SuppliersComponent {
  private readonly api = inject(ApiService);
  private readonly destroyRef = inject(DestroyRef);
  scores: SupplierScore[] = [];
  loading = true;
  error = '';
  readonly numberTr = numberTr;
  readonly Number = Number;

  constructor() {
    timer(0, 5000)
      .pipe(
        switchMap(() => this.api.supplierScores().pipe(
          catchError(() => {
            this.error = 'Tedarikçi skorları yüklenemedi.';
            this.loading = false;
            return EMPTY;
          }),
        )),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((result) => {
        this.scores = result.items;
        this.loading = false;
        this.error = '';
      });
  }

  pct(value: string): string {
    return `${numberTr(Number(value) * 100, 0)}%`;
  }

  reload(): void {
    this.loading = true;
    this.api.supplierScores().subscribe({
      next: (result) => {
        this.scores = result.items;
        this.loading = false;
        this.error = '';
      },
      error: () => {
        this.error = 'Tedarikçi skorları yüklenemedi.';
        this.loading = false;
      },
    });
  }
}
