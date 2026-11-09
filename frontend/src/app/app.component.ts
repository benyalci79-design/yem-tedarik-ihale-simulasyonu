import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  template: '<div class="app-shell"><header class="topbar"><a class="brand" routerLink="/"><span class="brand-mark">Yİ</span><span>Yem İhale <small>Simülasyonu</small></span></a><nav aria-label="Ana menü"><a routerLink="/" routerLinkActive="active" [routerLinkActiveOptions]="{ exact: true }">Özet</a><a routerLink="/products" routerLinkActive="active">Ürün Ayarları</a><a routerLink="/npc-rules" routerLinkActive="active">NPC Kuralları</a><a routerLink="/tenders" routerLinkActive="active">İhale Listesi</a></nav></header><main class="page-wrap"><router-outlet /></main></div>'
})
export class AppComponent {}
