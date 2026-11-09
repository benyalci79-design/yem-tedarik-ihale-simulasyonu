export interface SimulationState {
  is_running: boolean;
  elapsed_seconds: string;
  last_error: string | null;
}

export interface ActiveTender {
  id: number;
  code: string;
  status: string;
}

export interface Product {
  id: number;
  code: string;
  name: string;
  current_stock_kg: string;
  consumption_kg_per_min: string;
  critical_coverage_minutes: string;
  target_coverage_minutes: string;
  offer_window_seconds: number;
  coverage_minutes: string;
  active_tenders: ActiveTender[];
}

export interface NpcRule {
  id: number;
  product_id: number;
  product_name: string;
  npc_supplier_id: number;
  npc_code: string;
  npc_name: string;
  is_invited: boolean;
  response_probability: string;
  min_price: string;
  max_price: string;
  min_delivery_minutes: number;
  max_delivery_minutes: number;
}

export interface TenderSummary {
  id: number;
  code: string;
  product_id: number;
  product_name: string;
  quantity_ton: string;
  status: string;
  opened_at_seconds: string;
  offer_closes_at_seconds: string;
  evaluate_at_seconds: string;
  remaining_seconds: string;
  invited_count: number;
  offer_count: number;
  result_reason: string | null;
}

export interface TenderOffer {
  participation_id: number;
  npc_supplier_id: number;
  npc_name: string;
  offer_status: string;
  unit_price?: string;
  total_amount?: string;
  delivery_minutes?: number;
  submitted_at_seconds?: string;
  decision?: string;
  decision_reason?: string | null;
}

export interface TenderDetail extends TenderSummary {
  offers: TenderOffer[];
  awarded_at_seconds: string | null;
  delivery_due_at_seconds: string | null;
  delivered_at_seconds: string | null;
  delivery_status: string | null;
}
