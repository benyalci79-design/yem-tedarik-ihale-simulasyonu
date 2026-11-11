import { CommonModule } from '@angular/common';
import { Component, DestroyRef, inject } from '@angular/core';
import { catchError, EMPTY, finalize, switchMap, timer } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ApiService } from '../core/api.service';
import { SimulationState } from '../core/models';
import { numberTr } from './display';

/**
 * Üst barda duran ortak simülasyon kontrolü: Dur · 0,5x · 1x · 2x · 3x.
 * Seçili hız vurgulanır; simülasyon saati seçili hızla ilerler.
 */
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
      <span class="sim-error" *ngIf="error">{{ error }}</span>
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
    '.segmented button:disabled { opacity:.55; cursor:progress; }',
    '.sim-error { color:#fca5a5; font-size:.75rem; }',
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

  private tickClock(): void {
    if (!this.state) return;
    const speed = Number(this.state.speed) || 1;
    const running = this.state.is_running ? ((performance.now() - this.anchorTime) / 1000) * speed : 0;
    this.displayElapsed = Math.max(0, this.anchorSeconds + running);
  }

  private apply(state: SimulationState): void {
    // Sunucu değeri 1 sn'lik tick gecikmesiyle gelebilir; küçük geri farkları
    // yutup saatin geri sıçramasını engelliyoruz, büyük sapmada sunucuya oturuyoruz.
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
