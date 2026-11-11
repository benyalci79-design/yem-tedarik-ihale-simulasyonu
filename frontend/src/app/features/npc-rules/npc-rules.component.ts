import { CommonModule } from '@angular/common';
import { Component, DestroyRef, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { catchError, EMPTY, finalize } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ApiService, apiErrorMessage } from '../../core/api.service';
import { NpcRule } from '../../core/models';
import { numberTr } from '../../shared/display';

@Component({
  selector: 'app-npc-rules',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  template: `<section class="page-heading"><div><p class="eyebrow">DAVET KURALLARI</p><h1>NPC kuralları</h1><p class="lede">Ürün bazında davet, cevap olasılığı, fiyat ve teslim aralıklarını yönetin.</p></div><span class="info-chip">En az bir davetli kural zorunlu</span></section><div *ngIf="error" class="alert">{{ error }} <button class="link-button" (click)="load()">Yeniden dene</button></div><div *ngIf="loading" class="loading">NPC kuralları yükleniyor…</div><div class="rules-table" *ngIf="!loading"><div class="table-head"><span>Ürün / NPC</span><span>Davet</span><span>Cevap olasılığı</span><span>Fiyat aralığı (TL/ton)</span><span>Teslim (dk)</span><span></span></div><div class="table-row" *ngFor="let rule of rules"><div><strong>{{ rule.product_name }}</strong><small>{{ rule.npc_name }}</small></div><form [formGroup]="forms[rule.id]" (ngSubmit)="save(rule)" class="rule-form"><label class="switch"><input type="checkbox" formControlName="is_invited"><span></span><b>{{ forms[rule.id].get('is_invited')?.value ? 'Davetli' : 'Pasif' }}</b></label><label class="inline-field"><input type="number" formControlName="response_probability" min="0" max="1" step=".001"><span>{{ numberTr((forms[rule.id].get('response_probability')?.value ?? 0) * 100, 1) }}%</span></label><div class="range-fields"><input type="number" formControlName="min_price" min=".01" step=".01"><span>–</span><input type="number" formControlName="max_price" min=".01" step=".01"></div><div class="range-fields small"><input type="number" formControlName="min_delivery_minutes" min="1" max="60"><span>–</span><input type="number" formControlName="max_delivery_minutes" min="1" max="60"></div><button class="button" type="submit" [disabled]="forms[rule.id].invalid || saving[rule.id]">Kaydet</button></form><span class="row-error" *ngIf="formError[rule.id]">{{ formError[rule.id] }}</span></div></div><div class="empty-state" *ngIf="!loading && !rules.length">NPC kuralı bulunamadı.</div>`,
  styles: ['.page-heading,.table-head,.table-row { display:grid; grid-template-columns:2fr 1fr 1.5fr 2fr 1.5fr 80px; gap:1rem; align-items:center; }.page-heading { display:flex; justify-content:space-between; margin-bottom:2rem; }.eyebrow { color:#1d4ed8; font-size:.78rem; font-weight:800; letter-spacing:.08em; }.page-heading h1 { margin:.3rem 0; color:#111827; font-size:2.4rem; }.lede { color:#4b5563; }.info-chip { color:#1e3a8a; background:#dbeafe; padding:.55rem .75rem; border-radius:999px; font-weight:750; }.rules-table { background:#fff; border:1px solid #cbd5e1; border-radius:1rem; overflow:hidden; }.table-head { color:#374151; background:#f1f5f9; padding:1rem; font-weight:800; font-size:.85rem; }.table-row { position:relative; padding:1rem; border-top:1px solid #e5e7eb; }.table-row strong,.table-row small { display:block; }.table-row small { color:#4b5563; margin-top:.25rem; }.rule-form { display:contents; }.rule-form label { color:#374151; }.rule-form input { min-width:0; border:1px solid #64748b; border-radius:.45rem; padding:.55rem; color:#111827; background:#fff; }.rule-form input:focus { outline:3px solid #bfdbfe; border-color:#1d4ed8; }.inline-field { display:flex; align-items:center; gap:.45rem; }.inline-field input { width:5.4rem; }.inline-field span { color:#374151; font-weight:700; }.range-fields { display:flex; align-items:center; gap:.35rem; }.range-fields input { width:6rem; }.range-fields.small input { width:4.2rem; }.button { border:0; border-radius:.55rem; padding:.6rem .75rem; color:#fff; background:#1d4ed8; font-weight:750; cursor:pointer; }.button:disabled { opacity:.55; cursor:not-allowed; }.switch { display:flex; align-items:center; gap:.4rem; }.switch input { width:auto; }.switch b { font-size:.85rem; }.row-error { grid-column:1/-1; color:#991b1b; font-size:.85rem; }.alert { padding:.9rem 1rem; color:#991b1b; background:#fee2e2; border:1px solid #fca5a5; border-radius:.7rem; margin-bottom:1rem; }.link-button { border:0; background:transparent; color:#991b1b; text-decoration:underline; cursor:pointer; }.loading,.empty-state { padding:2rem; text-align:center; color:#334155; } @media(max-width:1000px){.table-head{display:none}.table-row{grid-template-columns:1fr; gap:.7rem}.rule-form{display:grid; grid-template-columns:repeat(2,1fr); gap:.7rem}.page-heading{align-items:flex-start; flex-direction:column}}']
})
export class NpcRulesComponent {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  private readonly destroyRef = inject(DestroyRef);
  rules: NpcRule[] = [];
  forms: Record<number, ReturnType<FormBuilder['group']>> = {};
  saving: Record<number, boolean> = {};
  formError: Record<number, string> = {};
  loading = true;
  error = '';
  readonly numberTr = numberTr;

  constructor() { this.load(); }

  load(): void {
    this.loading = true;
    this.error = '';
    this.api.npcRules().pipe(
      catchError(() => { this.error = 'NPC kuralları yüklenemedi.'; this.loading = false; return EMPTY; }),
      finalize(() => this.loading = false),
      takeUntilDestroyed(this.destroyRef)
    ).subscribe(result => {
      this.rules = result.items;
      this.error = '';
      for (const rule of this.rules) {
        this.forms[rule.id] = this.fb.group({
          is_invited: [rule.is_invited],
          response_probability: [Number(rule.response_probability), [Validators.required, Validators.min(0), Validators.max(1)]],
          min_price: [Number(rule.min_price), [Validators.required, Validators.min(.01)]],
          max_price: [Number(rule.max_price), [Validators.required, Validators.min(.01)]],
          min_delivery_minutes: [rule.min_delivery_minutes, [Validators.required, Validators.min(1), Validators.max(60)]],
          max_delivery_minutes: [rule.max_delivery_minutes, [Validators.required, Validators.min(1), Validators.max(60)]]
        });
      }
    });
  }

  save(rule: NpcRule): void {
    const form = this.forms[rule.id];
    if (form.invalid) return;
    const values = form.getRawValue();
    if (Number(values.max_price) < Number(values.min_price)) {
      this.formError[rule.id] = 'Maksimum fiyat minimum fiyattan küçük olamaz.';
      return;
    }
    if (Number(values.max_delivery_minutes) < Number(values.min_delivery_minutes)) {
      this.formError[rule.id] = 'Maksimum teslim süresi minimum teslim süresinden küçük olamaz.';
      return;
    }
    this.saving[rule.id] = true;
    this.formError[rule.id] = '';
    this.api.updateNpcRule(rule.id, values).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => { this.saving[rule.id] = false; this.load(); },
      error: (error: { error?: { message?: string } }) => {
        this.saving[rule.id] = false;
        this.formError[rule.id] = apiErrorMessage(error, 'Kural kaydedilemedi.');
      }
    });
  }
}
