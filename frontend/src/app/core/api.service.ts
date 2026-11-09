import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { NpcRule, Product, SimulationState, TenderDetail, TenderSummary } from './models';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/v1';

  simulation(): Observable<SimulationState> {
    return this.http.get<SimulationState>(this.base + '/simulation');
  }

  startSimulation(): Observable<SimulationState> {
    return this.http.post<SimulationState>(this.base + '/simulation/start', {});
  }

  pauseSimulation(): Observable<SimulationState> {
    return this.http.post<SimulationState>(this.base + '/simulation/pause', {});
  }

  products(): Observable<{ items: Product[] }> {
    return this.http.get<{ items: Product[] }>(this.base + '/products');
  }

  updateProduct(id: number, value: Partial<Product>): Observable<Product> {
    return this.http.patch<Product>(this.base + '/products/' + id, value);
  }

  npcRules(productId?: number): Observable<{ items: NpcRule[] }> {
    let params = new HttpParams();
    if (productId !== undefined) params = params.set('product_id', productId);
    return this.http.get<{ items: NpcRule[] }>(this.base + '/npc-rules', { params });
  }

  updateNpcRule(id: number, value: Partial<NpcRule>): Observable<NpcRule> {
    return this.http.patch<NpcRule>(this.base + '/npc-rules/' + id, value);
  }

  tenders(productId?: number, status?: string): Observable<{ items: TenderSummary[] }> {
    let params = new HttpParams();
    if (productId !== undefined) params = params.set('product_id', productId);
    if (status) params = params.set('status', status);
    return this.http.get<{ items: TenderSummary[] }>(this.base + '/tenders', { params });
  }

  tender(id: number): Observable<TenderDetail> {
    return this.http.get<TenderDetail>(this.base + '/tenders/' + id);
  }
}
