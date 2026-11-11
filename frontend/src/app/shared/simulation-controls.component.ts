import { CommonModule } from '@angular/common';
import { Component, DestroyRef, HostListener, inject } from '@angular/core';
import { catchError, EMPTY, finalize, switchMap, timer } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ApiService, apiErrorMessage } from '../core/api.service';
import { SimulationState } from '../core/models';
import { numberTr } from './display';

@Component({
  selector: 'app-simulation-controls',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="sim-controls">
      <span class="sim-clock" [class.paused]="!state?.is_running" [title]="state?.is_running ? 'Simülasyon saati' : 'Simülasyon durdu'">
        <i></i>{{ numberTr(displayElapsed, 1) }} sn
      </span>
      <div class="segmented" role="group" aria-label="Simülasyon hızı">
        <button type="button" [class.active]="stopped" [disabled]="pending" (click)="stop()">Dur</button>
        <button
          *ngFor="let speed of speeds"
          type="button"
          [class.active]="isActive(speed)"
          [disabled]="pending"
          (click)="setSpeed(speed)"
        >{{ speedLabel(speed) }}</button>
      </div>
      <button type="button" class="reset-button" [disabled]="pending" (click)="askReset()" title="Simülasyonu başlangıç durumuna döndür">Sıfırla</button>
      <span class="sim-error" *ngIf="error">{{ error }}</span>
    </div>

    <div class="modal-backdrop" *ngIf="resetOpen" (click)="cancelReset()">
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="reset-title" (click)="$event.stopPropagation()">
        <h2 id="reset-title">Simülasyonu sıfırlamak istediğinize emin misiniz?</h2>
        <p>
          Tüm ihaleler, teklifler, teslimatlar ve stok geçmişi silinip yerine demo geçmişi
          (geçmiş alımlar) yüklenecek. Ürün, NPC ve nakliyeci ayarları başlangıç değerlerine
          dönecek; simülasyon duraklatılacak. <strong>Bu işlem geri alınamaz.</strong>
        </p>
        <div class="modal-actions">
          <button type="button" class="button ghost" [disabled]="resetting" (click)="cancelReset()">Vazgeç</button>
          <button type="button" class="button danger" [disabled]="resetting" (click)="confirmReset()">
            {{ resetting ? 'Sıfırlanıyor…' : 'Evet, sıfırla' }}
          </button>
        </div>
        <p class="modal-error" *ngIf="resetError">{{ resetError }}</p>
      </div>
    </div>
  `,
  styles: [
    '.sim-controls { display:flex; align-items:center; gap:.6rem; flex-wrap:wrap; }',
    '.sim-clock { display:inline-flex; align-items:center; gap:.4rem; color:#e2e8f0; font-weight:750; font-variant-numeric:tabular-nums; font-size:.85rem; padding:.35rem .55rem; background:#1f2937; border-radius:.5rem; }',
    '.sim-clock i { width:.55rem; height:.55rem; border-radius:50%; background:#10b981; box-shadow:0 0 0 .2rem rgba(16,185,129,.25); }',
    '.sim-clock.paused i { background:#f59e0b; box-shadow:0 0 0 .2rem rgba(245,158,11,.25); }',
    '.segmented { display:inline-flex; border:1px solid #374151; border-radius:.55rem; overflow:hidden; }',
    '.segmented button { border:0; background:#1f2937; color:#d1d5db; font-size:.82rem; font-weight:750; padding:.4rem .6rem; cursor:pointer; border-right:1px solid #374151; }',
    '.segmented button:last-child { border-right:0; }',
    '.segmented button:hover:not(:disabled) { background:#374151; color:#fff; }',
    '.segmented button.active { background:#1d4ed8; color:#fff; }',
    '.reset-button { border:1px solid #7f1d1d; background:#1f2937; color:#fca5a5; font-size:.82rem; font-weight:750; padding:.4rem .65rem; border-radius:.55rem; cursor:pointer; }',
    '.reset-button:hover:not(:disabled) { background:#7f1d1d; color:#fff; }',
    '.reset-button:disabled, .segmented button:disabled { opacity:.55; cursor:progress; }',
    '.sim-error { color:#fca5a5; font-size:.75rem; }',
    '.modal-backdrop { position:fixed; inset:0; z-index:1000; display:grid; place-items:center; padding:1.5rem; background:rgba(15,23,42,.6); backdrop-filter:blur(2px); }',
    '.modal { width:min(520px,100%); background:#fff; color:#172033; border-radius:1rem; padding:1.5rem; box-shadow:0 24px 60px rgba(15,23,42,.35); }',
    '.modal h2 { margin:0 0 .6rem; font-size:1.25rem; color:#111827; }',
    '.modal p { margin:0 0 1.1rem; color:#374151; line-height:1.5; }',
    '.modal-actions { display:flex; justify-content:flex-end; gap:.6rem; }',
    '.button { border:0; border-radius:.6rem; padding:.65rem 1rem; font-weight:750; cursor:pointer; }',
    '.button.ghost { background:#e2e8f0; color:#1e293b; }',
    '.button.danger { background:#b91c1c; color:#fff; }',
    '.button:disabled { opacity:.6; cursor:not-allowed; }',
    '.modal-error { margin:.9rem 0 0; color:#991b1b; font-weight:700; }',
    '@media(max-width:760px){.modal-actions{flex-direction:column-reverse}.modal-actions .button{width:100%}}',
  ],
})
export class SimulationControlsComponent {
  private readonly api = inject(ApiService);
  private readonly destroyRef = inject(DestroyRef);
  readonly speeds = ['0.5', '1', '2', '3'];
  readonly numberTr = numberTr;
  state: SimulationState | null = null;
  displayElapsed = 0;
  pending = false;
  error = '';
  resetOpen = false;
  resetting = false;
  resetError = '';
  private anchorSeconds = 0;
  private anchorTime = performance.now();

  constructor() {
    timer(0, 2000)
      .pipe(
        switchMap(() => this.api.simulation().pipe(catchError(() => EMPTY))),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((state) => this.apply(state));
    timer(0, 250)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.tickClock());
  }

  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.resetOpen && !this.resetting) {
      this.cancelReset();
    }
  }

  get stopped(): boolean {
    return !this.state?.is_running;
  }

  speedLabel(speed: string): string {
    return speed === '0.5' ? '0,5x' : `${speed}x`;
  }

  isActive(speed: string): boolean {
    return Boolean(this.state?.is_running) && Number(this.state?.speed) === Number(speed);
  }

  stop(): void {
    if (this.pending) return;
    this.pending = true;
    this.error = '';
    this.api
      .pauseSimulation()
      .pipe(finalize(() => (this.pending = false)))
      .subscribe({
        next: (state) => this.apply(state),
        error: () => (this.error = 'Durdurulamadı'),
      });
  }

  setSpeed(speed: string): void {
    if (this.pending) return;
    this.pending = true;
    this.error = '';
    this.api
      .setSpeed(speed)
      .pipe(finalize(() => (this.pending = false)))
      .subscribe({
        next: (state) => this.apply(state),
        error: () => (this.error = 'Hız değiştirilemedi'),
      });
  }

  askReset(): void {
    this.resetError = '';
    this.resetOpen = true;
  }

  cancelReset(): void {
    if (this.resetting) return;
    this.resetOpen = false;
    this.resetError = '';
  }

  confirmReset(): void {
    if (this.resetting) return;
    this.resetting = true;
    this.resetError = '';
    this.api
      .resetSimulation()
      .pipe(finalize(() => (this.resetting = false)))
      .subscribe({
        next: () => {
          this.resetOpen = false;
          window.location.assign('/');
        },
        error: (error: unknown) => {
          this.resetError = apiErrorMessage(error, 'Sıfırlama başarısız oldu.');
        },
      });
  }

  private tickClock(): void {
    if (!this.state) return;
    const speed = Number(this.state.speed) || 1;
    const running = this.state.is_running ? ((performance.now() - this.anchorTime) / 1000) * speed : 0;
    this.displayElapsed = Math.max(0, this.anchorSeconds + running);
  }

  private apply(state: SimulationState): void {
    const server = Number(state.elapsed_seconds) || 0;
    const speed = Number(state.speed) || 1;
    const local = this.displayElapsed;
    this.state = state;
    if (!state.is_running) {
      this.anchorSeconds = server;
    } else {
      const drift = local - server;
      this.anchorSeconds = drift > speed * 2 || drift < -speed * 3 ? server : Math.max(server, local);
    }
    this.anchorTime = performance.now();
    this.displayElapsed = this.anchorSeconds;
  }
}
