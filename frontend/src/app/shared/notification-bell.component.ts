import { CommonModule } from '@angular/common';
import { Component, DestroyRef, HostListener, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { catchError, EMPTY, switchMap, timer } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ApiService } from '../core/api.service';
import { AppNotification } from '../core/models';

const STORAGE_KEY = 'yem-notifications-read';

@Component({
  selector: 'app-notification-bell',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="bell-wrap">
      <button type="button" class="bell" [class.has-unread]="unreadCount > 0" (click)="toggle()" [attr.aria-expanded]="open" aria-label="Bildirimler">
        <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
          <path d="M12 3a5 5 0 0 0-5 5v3.2c0 .9-.35 1.75-.98 2.38L4.6 15.6c-.6.6-.18 1.65.67 1.65h13.46c.85 0 1.27-1.05.67-1.65l-1.42-1.42A3.36 3.36 0 0 1 17 11.2V8a5 5 0 0 0-5-5Z" fill="currentColor"/>
          <path d="M9.5 19a2.5 2.5 0 0 0 5 0" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
        <span class="badge" *ngIf="unreadCount > 0">{{ unreadCount }}</span>
      </button>

      <div class="overlay" *ngIf="open" (click)="close()"></div>

      <section class="panel" *ngIf="open" role="dialog" aria-label="Bildirim kutusu">
        <header class="panel-head">
          <strong>Bildirimler</strong>
          <button type="button" class="link" *ngIf="unreadCount > 0" (click)="markAllRead()">Tümünü okundu işaretle</button>
        </header>
        <div class="panel-body" *ngIf="items.length; else empty">
          <a
            *ngFor="let item of items"
            [class]="'item ' + item.severity + (isRead(item.id) ? '' : ' unread')"
            [routerLink]="item.link"
            (click)="markRead(item.id); close()"
          >
            <span class="dot"></span>
            <span class="content"><strong>{{ item.title }}</strong><small>{{ item.detail }}</small></span>
          </a>
        </div>
        <ng-template #empty><p class="empty">Şu an bildirim yok.</p></ng-template>
      </section>
    </div>
  `,
  styles: [
    '.bell-wrap { position:relative; display:inline-flex; flex-shrink:0; }',
    '.bell { position:relative; display:grid; place-items:center; width:2.1rem; height:2.1rem; border-radius:.55rem; border:1px solid #374151; background:#1f2937; color:#d1d5db; cursor:pointer; }',
    '.bell:hover { background:#374151; color:#fff; }.bell.has-unread { color:#fff; border-color:#1d4ed8; }',
    '.badge { position:absolute; top:-.35rem; right:-.35rem; min-width:1.15rem; height:1.15rem; padding:0 .25rem; border-radius:999px; background:#dc2626; color:#fff; font-size:.68rem; font-weight:800; display:grid; place-items:center; }',
    '.overlay { position:fixed; inset:0; z-index:40; background:transparent; }',
    '.panel { position:absolute; right:0; top:2.6rem; z-index:50; width:min(380px, 90vw); background:#fff; color:#172033; border:1px solid #cbd5e1; border-radius:.8rem; box-shadow:0 18px 40px rgba(15,23,42,.3); overflow:hidden; }',
    '.panel-head { display:flex; justify-content:space-between; align-items:center; gap:.5rem; padding:.75rem .9rem; border-bottom:1px solid #e5e7eb; }',
    '.panel-head .link { border:0; background:transparent; color:#1d4ed8; font-size:.78rem; font-weight:750; cursor:pointer; }',
    '.panel-body { max-height:340px; overflow:auto; display:grid; }',
    '.item { display:flex; gap:.6rem; padding:.7rem .9rem; text-decoration:none; color:#172033; border-top:1px solid #f1f5f9; }',
    '.item:first-child { border-top:0; }.item:hover { background:#f8fafc; }.item.unread { background:#eff6ff; }',
    '.item .dot { width:.55rem; height:.55rem; margin-top:.35rem; border-radius:50%; flex:none; background:#94a3b8; }',
    '.item.warning .dot { background:#f59e0b; }.item.danger .dot { background:#dc2626; }.item.info .dot { background:#2563eb; }',
    '.item .content { display:grid; gap:.15rem; }.item small { color:#475569; font-size:.8rem; }',
    '.empty { margin:0; padding:1.5rem 1rem; text-align:center; color:#475569; }',
  ],
})
export class NotificationBellComponent {
  private readonly api = inject(ApiService);
  private readonly destroyRef = inject(DestroyRef);
  items: AppNotification[] = [];
  open = false;
  private readIds = new Set<string>(this.loadRead());

  constructor() {
    timer(0, 5000)
      .pipe(
        switchMap(() => this.api.notifications().pipe(catchError(() => EMPTY))),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((result) => {
        this.items = result.items;
        const validIds = new Set(this.items.map((item) => item.id));
        for (const id of [...this.readIds]) {
          if (!validIds.has(id)) this.readIds.delete(id);
        }
      });
  }

  get unreadCount(): number {
    return this.items.filter((item) => !this.readIds.has(item.id)).length;
  }

  @HostListener('document:keydown.escape')
  onEscape(): void {
    this.open = false;
  }

  toggle(): void {
    this.open = !this.open;
  }

  close(): void {
    this.open = false;
  }

  isRead(id: string): boolean {
    return this.readIds.has(id);
  }

  markRead(id: string): void {
    this.readIds.add(id);
    this.persist();
  }

  markAllRead(): void {
    for (const item of this.items) this.readIds.add(item.id);
    this.persist();
  }

  private persist(): void {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify([...this.readIds]));
    } catch {
      return;
    }
  }

  private loadRead(): string[] {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  }
}
