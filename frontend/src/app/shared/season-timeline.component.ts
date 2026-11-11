import { CommonModule } from '@angular/common';
import { Component, DestroyRef, inject } from '@angular/core';
import { catchError, EMPTY, switchMap, timer } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ApiService } from '../core/api.service';

@Component({
  selector: 'app-season-timeline',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div
      class="season-timeline"
      role="slider"
      aria-label="Mevsim zaman çizelgesi"
      [attr.aria-valuemin]="0"
      [attr.aria-valuemax]="1"
      [attr.aria-valuenow]="progress"
      (pointerdown)="onDown($event)"
      (pointermove)="onMove($event)"
      (pointerup)="onUp($event)"
      (pointercancel)="onUp($event)"
    >
      <div class="bands">
        <span class="band spring">İlkbahar</span>
        <span class="band summer">Yaz</span>
        <span class="band autumn">Sonbahar</span>
        <span class="band winter">Kış</span>
      </div>

      <div class="fill" [style.width.%]="progress * 100"></div>

      <div class="handle" [style.left.%]="progress * 100">
        <i></i>
      </div>

      <div class="readout">
        <strong>{{ label }}</strong>
        <span>Ay {{ month }}</span>
      </div>
    </div>
  `,
  styles: [
    '.season-timeline { position:relative; height:44px; background:#111827; border-top:1px solid #1f2937; border-bottom:1px solid #1f2937; overflow:hidden; cursor:ew-resize; user-select:none; touch-action:none; }',
    '.bands { position:absolute; inset:0; display:grid; grid-template-columns:repeat(4, 1fr); }',
    '.band { display:flex; align-items:center; justify-content:center; font-size:.7rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase; color:rgba(255,255,255,.72); border-right:1px solid rgba(255,255,255,.08); }',
    '.band:last-child { border-right:0; }',
    '.band.spring { background:linear-gradient(180deg, rgba(22,163,74,.28), rgba(22,163,74,.12)); }',
    '.band.summer { background:linear-gradient(180deg, rgba(245,158,11,.28), rgba(245,158,11,.12)); }',
    '.band.autumn { background:linear-gradient(180deg, rgba(234,88,12,.28), rgba(234,88,12,.12)); }',
    '.band.winter { background:linear-gradient(180deg, rgba(96,165,250,.28), rgba(96,165,250,.12)); }',
    '.fill { position:absolute; top:0; bottom:0; left:0; background:rgba(255,255,255,.08); pointer-events:none; }',
    '.handle { position:absolute; top:0; bottom:0; width:2px; background:#f8fafc; pointer-events:none; transform:translateX(-1px); }',
    '.handle i { position:absolute; top:-1px; left:50%; width:11px; height:11px; border-radius:50%; background:#f8fafc; transform:translate(-50%, -30%); box-shadow:0 0 0 3px rgba(248,250,252,.18); }',
    '.readout { position:absolute; right:.9rem; top:50%; transform:translateY(-50%); display:flex; align-items:baseline; gap:.45rem; padding:.2rem .55rem; background:rgba(15,23,42,.75); border:1px solid rgba(255,255,255,.14); border-radius:999px; color:#e2e8f0; font-size:.78rem; pointer-events:none; }',
    '.readout strong { color:#fff; }',
    '.readout span { color:#cbd5e1; }',
  ],
})
export class SeasonTimelineComponent {
  private readonly api = inject(ApiService);
  private readonly destroyRef = inject(DestroyRef);
  progress = 0;
  private dragging = false;

  constructor() {
    timer(0, 2000)
      .pipe(
        switchMap(() => this.api.simulation().pipe(catchError(() => EMPTY))),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((state) => {
        if (!this.dragging) {
          this.progress = Number(state.season_progress) || 0;
        }
      });
  }

  get label(): string {
    if (this.progress < 0.25) return 'İlkbahar';
    if (this.progress < 0.5) return 'Yaz';
    if (this.progress < 0.75) return 'Sonbahar';
    return 'Kış';
  }

  get month(): number {
    return Math.floor(this.progress * 12) + 1;
  }

  onDown(event: PointerEvent): void {
    this.dragging = true;
    const element = event.currentTarget as HTMLElement;
    try {
      element.setPointerCapture(event.pointerId);
    } catch {
      /* sentetik olaylarda pointer capture kullanılamayabilir */
    }
    this.updateFromEvent(event);
  }

  onMove(event: PointerEvent): void {
    if (!this.dragging) return;
    this.updateFromEvent(event);
  }

  onUp(event: PointerEvent): void {
    if (!this.dragging) return;
    this.updateFromEvent(event);
    this.dragging = false;
    this.api
      .setSeason(this.progress)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (state) => (this.progress = Number(state.season_progress) || this.progress),
        error: () => undefined,
      });
  }

  private updateFromEvent(event: PointerEvent): void {
    const element = event.currentTarget as HTMLElement;
    const rect = element.getBoundingClientRect();
    if (rect.width === 0) return;
    const ratio = (event.clientX - rect.left) / rect.width;
    this.progress = Math.max(0, Math.min(1, ratio));
  }
}
