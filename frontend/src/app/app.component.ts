import { Component, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { SimulationControlsComponent } from './shared/simulation-controls.component';
import { NotificationBellComponent } from './shared/notification-bell.component';
import { SeasonTimelineComponent } from './shared/season-timeline.component';
import { ToastContainerComponent } from './shared/toast-container.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    RouterLink,
    RouterLinkActive,
    RouterOutlet,
    SimulationControlsComponent,
    NotificationBellComponent,
    SeasonTimelineComponent,
    ToastContainerComponent,
  ],
  template: '<div class="app-shell"><div class="app-header"><header class="topbar"><a class="brand" href="/" aria-label="Yem İhale Simülasyonu ana sayfa" (click)="goHome($event)"><span class="brand-mark">Yİ</span><span>Yem İhale <small>Simülasyonu</small></span></a><nav aria-label="Ana menü"><a routerLink="/" routerLinkActive="active" [routerLinkActiveOptions]="{ exact: true }">Özet</a><a routerLink="/products" routerLinkActive="active">Ürün Ayarları</a><a routerLink="/npc-rules" routerLinkActive="active">NPC Kuralları</a><a routerLink="/tenders" routerLinkActive="active">İhale Listesi</a><a routerLink="/shipping" routerLinkActive="active">Nakliye</a><a routerLink="/suppliers" routerLinkActive="active">Tedarikçiler</a></nav><div class="topbar-tools"><app-simulation-controls /><app-notification-bell /></div></header><app-season-timeline /></div><main class="page-wrap"><router-outlet /></main><app-toast-container /></div>'
})
export class AppComponent {
  private readonly router = inject(Router);

  goHome(event: MouseEvent): void {
    event.preventDefault();
    if (this.router.url !== '/') void this.router.navigateByUrl('/');
  }
}
