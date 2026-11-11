import { CommonModule } from '@angular/common';
import { Component, inject } from '@angular/core';
import { ToastService } from './toast.service';

@Component({
  selector: 'app-toast-container',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="toasts" aria-live="polite">
      <div class="toast {{ toast.type }}" *ngFor="let toast of toastService.messages | async">
        <span class="icon">{{ toast.type === 'success' ? '✓' : toast.type === 'error' ? '!' : 'i' }}</span>
        <span>{{ toast.message }}</span>
        <button type="button" class="close" (click)="toastService.dismiss(toast.id)" aria-label="Kapat">×</button>
      </div>
    </div>
  `,
  styles: [
    '.toasts { position:fixed; right:1.2rem; bottom:1.2rem; z-index:300; display:grid; gap:.5rem; max-width:min(420px, 90vw); }',
    '.toast { display:flex; align-items:center; gap:.6rem; padding:.7rem .85rem; border-radius:.65rem; background:#111827; color:#f8fafc; box-shadow:0 12px 30px rgba(15,23,42,.35); font-size:.9rem; border-left:4px solid #10b981; animation:slide .18s ease-out; }',
    '.toast.error { border-left-color:#ef4444; }.toast.info { border-left-color:#3b82f6; }',
    '.toast .icon { display:grid; place-items:center; width:1.3rem; height:1.3rem; border-radius:50%; background:rgba(255,255,255,.14); font-weight:800; font-size:.8rem; }',
    '.toast .close { margin-left:auto; border:0; background:transparent; color:#cbd5e1; font-size:1.1rem; cursor:pointer; line-height:1; }',
    '@keyframes slide { from { transform:translateY(6px); opacity:0; } to { transform:translateY(0); opacity:1; } }',
  ],
})
export class ToastContainerComponent {
  readonly toastService = inject(ToastService);
}
