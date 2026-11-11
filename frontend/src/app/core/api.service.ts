import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  AppNotification,
  BudgetState,
  Carrier,
  HistoryPoint,
  NpcRule,
  Product,
  PurchaseStatsItem,
  Shipment,
  SimulationState,
  StockMetrics,
  SupplierScore,
  TenderDetail,
  TenderSummary,
} from './models';

export function apiErrorMessage(error: unknown, fallback: string): string {
  const response = error as { error?: { error?: { message?: unknown } } };
  const message = response?.error?.error?.message;
  return typeof message === 'string' && message.length > 0 ? message : fallback;
}

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

  setSpeed(speed: string): Observable<SimulationState> {
    return this.http.post<SimulationState>(this.base + '/simulation/speed', { speed });
  }

  setSeason(progress: number): Observable<SimulationState> {
    return this.http.post<SimulationState>(this.base + '/simulation/season', {
      progress: progress.toFixed(4),
    });
  }

  resetSimulation(): Observable<SimulationState> {
    return this.http.post<SimulationState>(this.base + '/simulation/reset', {});
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

  createTender(productId: number, quantityTon: number): Observable<TenderDetail> {
    return this.http.post<TenderDetail>(this.base + '/tenders', {
      product_id: productId,
      quantity_ton: quantityTon.toFixed(3),
    });
  }

  acceptOffer(tenderId: number, participationId: number, quantityKg: number): Observable<TenderDetail> {
    return this.http.post<TenderDetail>(this.base + '/tenders/' + tenderId + '/accept', {
      participation_id: participationId,
      quantity_kg: quantityKg.toFixed(3),
    });
  }

  finalizeTender(tenderId: number): Observable<TenderDetail> {
    return this.http.post<TenderDetail>(this.base + '/tenders/' + tenderId + '/finalize', {});
  }

  carriers(): Observable<{ items: Carrier[] }> {
    return this.http.get<{ items: Carrier[] }>(this.base + '/carriers');
  }

  shipments(status?: string): Observable<{ items: Shipment[] }> {
    let params = new HttpParams();
    if (status) params = params.set('status', status);
    return this.http.get<{ items: Shipment[] }>(this.base + '/shipments', { params });
  }

  assignCarrier(awardId: number, carrierId: number): Observable<Shipment> {
    return this.http.post<Shipment>(this.base + '/shipments/' + awardId + '/assign-carrier', {
      carrier_id: carrierId,
    });
  }

  stockMetrics(): Observable<StockMetrics> {
    return this.http.get<StockMetrics>(this.base + '/stock-metrics');
  }

  stockHistory(limit = 300): Observable<{ items: HistoryPoint[] }> {
    return this.http.get<{ items: HistoryPoint[] }>(this.base + '/stock-metrics/history', {
      params: new HttpParams().set('limit', limit),
    });
  }

  purchaseStats(): Observable<{ items: PurchaseStatsItem[] }> {
    return this.http.get<{ items: PurchaseStatsItem[] }>(this.base + '/purchase-stats');
  }

  budget(): Observable<BudgetState> {
    return this.http.get<BudgetState>(this.base + '/budget');
  }

  updateBudget(monthlyLimit: number): Observable<BudgetState> {
    return this.http.patch<BudgetState>(this.base + '/budget', {
      monthly_limit_tl: monthlyLimit.toFixed(2),
    });
  }

  supplierScores(): Observable<{ items: SupplierScore[] }> {
    return this.http.get<{ items: SupplierScore[] }>(this.base + '/supplier-scores');
  }

  notifications(): Observable<{ items: AppNotification[] }> {
    return this.http.get<{ items: AppNotification[] }>(this.base + '/notifications');
  }
}
