import { Component, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { SimulationControlsComponent } from './shared/simulation-controls.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, RouterOutlet, SimulationControlsComponent],
  template: '<div class="app-shell"><header class="topbar"><a class="brand" href="/" aria-label="Yem İhale Simülasyonu ana sayfa" (click)="goHome($event)"><span class="brand-mark">Yİ</span><span>Yem İhale <small>Simülasyonu</small></span></a><nav aria-label="Ana menü"><a routerLink="/" routerLinkActive="active" [routerLinkActiveOptions]="{ exact: true }">Özet</a><a routerLink="/products" routerLinkActive="active">Ürün Ayarları</a><a routerLink="/npc-rules" routerLinkActive="active">NPC Kuralları</a><a routerLink="/tenders" routerLinkActive="active">İhale Listesi</a><a routerLink="/shipping" routerLinkActive="active">Nakliye</a><a routerLink="/suppliers" routerLinkActive="active">Tedarikçiler</a></nav><app-simulation-controls /></header><main class="page-wrap"><router-outlet /></main></div>'
})
export class AppComponent {
  private readonly router = inject(Router);

  goHome(event: MouseEvent): void {
    event.preventDefault();
    if (this.router.url !== '/') void this.router.navigateByUrl('/');
  }
}
