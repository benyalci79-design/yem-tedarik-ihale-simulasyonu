import { Component, Input } from '@angular/core';
import { statusIcon, statusLabel } from './display';

@Component({
  selector: 'app-status-badge',
  standalone: true,
  template: '<span class="status-badge status-{{ status }}" [attr.aria-label]="statusLabel(status)"><span aria-hidden="true">{{ statusIcon(status) }}</span> {{ statusLabel(status) }}</span>',
  styles: [
    '.status-badge { display: inline-flex; align-items: center; gap: .4rem; border-radius: 999px; padding: .35rem .65rem; font-weight: 750; font-size: .875rem; white-space: nowrap; }',
    '.status-OPEN { color: #047857; background: #d1fae5; }',
    '.status-EVALUATION { color: #92400e; background: #fef3c7; }',
    '.status-AWARDED { color: #166534; background: #dcfce7; }',
    '.status-DELIVERED { color: #166534; background: #bbf7d0; }',
    '.status-NO_AWARD { color: #374151; background: #e5e7eb; }'
  ]
})
export class StatusBadgeComponent {
  @Input({ required: true }) status = '';
  readonly statusLabel = statusLabel;
  readonly statusIcon = statusIcon;
}
