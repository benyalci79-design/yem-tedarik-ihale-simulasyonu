import { Routes } from '@angular/router';
import { DashboardComponent } from './features/dashboard/dashboard.component';
import { ProductsComponent } from './features/products/products.component';
import { NpcRulesComponent } from './features/npc-rules/npc-rules.component';
import { TendersComponent } from './features/tenders/tenders.component';
import { TenderDetailComponent } from './features/tenders/tender-detail.component';

export const routes: Routes = [
  { path: '', component: DashboardComponent },
  { path: 'products', component: ProductsComponent },
  { path: 'npc-rules', component: NpcRulesComponent },
  { path: 'tenders', component: TendersComponent },
  { path: 'tenders/:id', component: TenderDetailComponent },
  { path: '**', redirectTo: '' }
];
