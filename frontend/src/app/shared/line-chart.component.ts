import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { ChartSeries } from '../core/models';
import { numberTr } from './display';

@Component({
  selector: 'app-line-chart',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="chart-card">
      <div class="legend" *ngIf="series.length">
        <button
          *ngFor="let item of series"
          type="button"
          class="legend-item"
          [class.off]="hidden[item.id]"
          (click)="toggle(item.id)"
        >
          <svg width="34" height="12" aria-hidden="true">
            <line x1="0" y1="6" x2="34" y2="6" [attr.stroke]="item.color" stroke-width="3" [attr.stroke-dasharray]="item.dash" />
          </svg>
          <span>{{ item.label }}</span>
        </button>
      </div>

      <ng-container *ngIf="hasData; else emptyState">
        <div class="plot">
          <svg [attr.viewBox]="'0 0 ' + width + ' ' + height" role="img" [attr.aria-label]="ariaLabel">
            <line
              *ngFor="let tick of yTicks"
              [attr.x1]="pad.left"
              [attr.x2]="width - pad.right"
              [attr.y1]="y(tick)"
              [attr.y2]="y(tick)"
              stroke="#e5e7eb"
              stroke-width="1"
            />
            <text
              *ngFor="let tick of yTicks"
              [attr.x]="pad.left - 10"
              [attr.y]="y(tick) + 4"
              text-anchor="end"
              class="axis-label"
            >{{ numberTr(tick, digits) }}</text>

            <polyline
              *ngFor="let item of visibleSeries"
              [attr.points]="points(item.values)"
              fill="none"
              [attr.stroke]="item.color"
              [attr.stroke-dasharray]="item.dash"
              stroke-width="2.5"
              stroke-linejoin="round"
              stroke-linecap="round"
            />

            <g *ngFor="let item of visibleSeries">
              <ng-container *ngFor="let index of markerIndices">
                <circle
                  *ngIf="item.marker === 'circle'"
                  [attr.cx]="x(index)"
                  [attr.cy]="y(item.values[index])"
                  r="3.2"
                  [attr.fill]="item.color"
                />
                <rect
                  *ngIf="item.marker === 'square'"
                  [attr.x]="x(index) - 3"
                  [attr.y]="y(item.values[index]) - 3"
                  width="6"
                  height="6"
                  [attr.fill]="item.color"
                />
                <polygon
                  *ngIf="item.marker === 'triangle'"
                  [attr.points]="triangle(x(index), y(item.values[index]))"
                  [attr.fill]="item.color"
                />
              </ng-container>
            </g>

            <text *ngFor="let label of xAxisLabels" [attr.x]="label.x" [attr.y]="height - 10" text-anchor="middle" class="axis-label">
              {{ label.text }}
            </text>

            <g *ngIf="hoverIndex !== null">
              <line
                [attr.x1]="x(hoverIndex)"
                [attr.x2]="x(hoverIndex)"
                [attr.y1]="pad.top"
                [attr.y2]="height - pad.bottom"
                stroke="#94a3b8"
                stroke-width="1"
                stroke-dasharray="4 3"
              />
              <circle
                *ngFor="let item of visibleSeries"
                [attr.cx]="x(hoverIndex)"
                [attr.cy]="y(item.values[hoverIndex])"
                r="4"
                fill="#fff"
                [attr.stroke]="item.color"
                stroke-width="2.5"
              />
            </g>

            <rect
              [attr.x]="pad.left"
              [attr.y]="pad.top"
              [attr.width]="plotWidth"
              [attr.height]="plotHeight"
              fill="transparent"
              (mousemove)="onMove($event)"
              (mouseleave)="hoverIndex = null"
            />
          </svg>

          <div class="tooltip" *ngIf="hoverIndex !== null" [style.left.%]="hoverPercent">
            <strong>{{ xLabels[hoverIndex] }}</strong>
            <span *ngFor="let row of tooltipRows" class="tooltip-row">
              <i [style.background]="row.color"></i>{{ row.label }}: {{ row.value }}
            </span>
          </div>
        </div>
      </ng-container>

      <ng-template #emptyState>
        <p class="empty">{{ emptyText }}</p>
      </ng-template>
    </div>
  `,
  styles: [
    '.chart-card { background:#fff; border:1px solid #cbd5e1; border-radius:1rem; padding:1rem 1.1rem; }',
    '.legend { display:flex; flex-wrap:wrap; gap:.4rem; margin-bottom:.6rem; }',
    '.legend-item { display:flex; align-items:center; gap:.4rem; border:1px solid #cbd5e1; background:#f8fafc; border-radius:999px; padding:.3rem .6rem; font-size:.82rem; font-weight:700; color:#172033; cursor:pointer; white-space:nowrap; }',
    '.legend-item.off { opacity:.45; text-decoration:line-through; }',
    '.plot { position:relative; }',
    'svg { width:100%; height:auto; display:block; }',
    '.axis-label { font-size:12px; fill:#475569; font-weight:600; }',
    '.empty { margin:0; padding:2.5rem 1rem; text-align:center; color:#475569; background:#f8fafc; border:1px dashed #94a3b8; border-radius:.7rem; }',
    '.tooltip { position:absolute; top:.4rem; transform:translateX(-50%); display:grid; gap:.15rem; padding:.5rem .65rem; background:#111827; color:#fff; border-radius:.5rem; font-size:.78rem; pointer-events:none; white-space:nowrap; box-shadow:0 6px 18px rgba(15,23,42,.25); }',
    '.tooltip-row { display:flex; align-items:center; gap:.35rem; }',
    '.tooltip-row i { width:.55rem; height:.55rem; border-radius:50%; display:inline-block; }',
  ],
})
export class LineChartComponent {
  @Input() series: ChartSeries[] = [];
  @Input() xLabels: string[] = [];
  @Input() digits = 0;
  @Input() emptyText = 'Grafik için yeterli veri yok.';
  @Input() ariaLabel = 'Zaman serisi grafiği';

  readonly width = 760;
  readonly height = 280;
  readonly pad = { top: 18, right: 18, bottom: 38, left: 78 };
  readonly numberTr = numberTr;
  hidden: Record<string, boolean> = {};
  hoverIndex: number | null = null;

  get visibleSeries(): ChartSeries[] {
    return this.series.filter((item) => !this.hidden[item.id]);
  }

  get pointCount(): number {
    return this.series.length ? Math.max(...this.series.map((item) => item.values.length)) : 0;
  }

  get hasData(): boolean {
    return this.pointCount >= 2 && this.visibleSeries.length > 0;
  }

  get plotWidth(): number {
    return this.width - this.pad.left - this.pad.right;
  }

  get plotHeight(): number {
    return this.height - this.pad.top - this.pad.bottom;
  }

  get bounds(): { min: number; max: number } {
    const values = this.visibleSeries.flatMap((item) => item.values);
    if (!values.length) {
      return { min: 0, max: 1 };
    }
    const min = Math.min(...values);
    const max = Math.max(...values);
    if (min === max) {
      const margin = Math.max(Math.abs(min) * 0.05, 1);
      return { min: min - margin, max: max + margin };
    }
    const span = max - min;
    const margin = span * 0.08;
    return { min: min >= 0 ? Math.max(0, min - margin) : min - margin, max: max + margin };
  }

  get yTicks(): number[] {
    const { min, max } = this.bounds;
    return Array.from({ length: 5 }, (_, index) => min + ((max - min) * index) / 4);
  }

  get xAxisLabels(): { x: number; text: string }[] {
    const count = this.pointCount;
    if (count < 2) {
      return [];
    }
    const wanted = Math.min(6, count);
    return Array.from({ length: wanted }, (_, index) => {
      const point = Math.round((index * (count - 1)) / (wanted - 1));
      return { x: this.x(point), text: this.xLabels[point] ?? '' };
    });
  }

  get markerIndices(): number[] {
    const count = this.pointCount;
    if (count === 0) {
      return [];
    }
    if (count <= 24) {
      return Array.from({ length: count }, (_, index) => index);
    }
    return [0, count - 1];
  }

  get hoverPercent(): number {
    if (this.hoverIndex === null) {
      return 0;
    }
    return (this.x(this.hoverIndex) / this.width) * 100;
  }

  get tooltipRows(): { label: string; value: string; color: string }[] {
    if (this.hoverIndex === null) {
      return [];
    }
    return this.visibleSeries.map((item) => ({
      label: item.label,
      value: numberTr(item.values[this.hoverIndex as number] ?? 0, this.digits),
      color: item.color,
    }));
  }

  x(index: number): number {
    const count = this.pointCount;
    if (count <= 1) {
      return this.pad.left;
    }
    return this.pad.left + (index / (count - 1)) * this.plotWidth;
  }

  y(value: number): number {
    const { min, max } = this.bounds;
    const ratio = (value - min) / (max - min);
    return this.pad.top + (1 - ratio) * this.plotHeight;
  }

  points(values: number[]): string {
    return values.map((value, index) => `${this.x(index).toFixed(1)},${this.y(value).toFixed(1)}`).join(' ');
  }

  triangle(cx: number, cy: number): string {
    return `${cx},${cy - 4} ${cx + 4},${cy + 3} ${cx - 4},${cy + 3}`;
  }

  toggle(id: string): void {
    this.hidden = { ...this.hidden, [id]: !this.hidden[id] };
    this.hoverIndex = null;
  }

  onMove(event: MouseEvent): void {
    const svg = event.currentTarget as SVGGraphicsElement;
    const rect = svg.getBoundingClientRect();
    if (rect.width === 0) {
      return;
    }
    const svgX = ((event.clientX - rect.left) / rect.width) * this.width;
    const count = this.pointCount;
    if (count < 2) {
      return;
    }
    const index = Math.round(((svgX - this.pad.left) / this.plotWidth) * (count - 1));
    this.hoverIndex = Math.max(0, Math.min(count - 1, index));
  }
}
