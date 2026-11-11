export interface SimulationState {
  is_running: boolean;
  elapsed_seconds: string;
  speed: string;
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
  capacity_kg: string;
  avg_cost_per_kg: string;
  last_purchase_unit_price: string;
  loss_percent: string;
  season_amplitude: string;
  season_factor: string;
  incoming_kg: string;
  free_capacity_kg: string;
  stock_value_tl: string;
  suggested_quantity_ton: string;
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
  freight_included: boolean;
  min_available_kg: string;
  max_available_kg: string;
}

export interface TenderOffer {
  participation_id: number;
  npc_supplier_id: number;
  npc_name: string;
  offer_status: string;
  unit_price?: string;
  unit_price_per_kg?: string;
  offered_quantity_kg?: string;
  accepted_quantity_kg?: string;
  delivery_minutes?: number;
  freight_included?: boolean;
  season_factor?: string;
  submitted_at_seconds?: string;
  decision?: string;
  decision_reason?: string | null;
  max_acceptable_kg?: string;
}

export interface TenderAward {
  id: number;
  participation_id: number;
  npc_supplier_id: number;
  npc_name: string;
  quantity_kg: string;
  unit_price_per_ton: string;
  unit_price_per_kg: string;
  freight_included: boolean;
  carrier_id: number | null;
  carrier_name: string | null;
  carrier_price_per_ton: string | null;
  status: string;
  loss_kg: string;
  accepted_kg: string;
  accepted_at_seconds: string;
  carrier_assigned_at_seconds: string | null;
  delivery_due_at_seconds: string | null;
  delivered_at_seconds: string | null;
  landed_cost_tl: string | null;
  remaining_seconds: string | null;
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
  accepted_total_kg: string;
  remaining_need_kg: string;
  free_capacity_kg: string;
  product_stock_kg: string;
  product_capacity_kg: string;
  product_avg_cost_per_kg: string;
  product_last_purchase_unit_price: string;
  product_loss_percent: string;
  product_season_factor: string;
  result_reason: string | null;
  awards: TenderAward[];
}

export interface TenderDetail extends TenderSummary {
  offers: TenderOffer[];
  awarded_at_seconds: string | null;
  delivery_due_at_seconds: string | null;
  delivered_at_seconds: string | null;
  delivery_status: string | null;
  budget_remaining_tl: string;
}

export interface Carrier {
  id: number;
  code: string;
  name: string;
  price_per_ton: string;
  price_per_kg: string;
  transit_minutes: number;
  is_active: boolean;
}

export interface Shipment {
  award_id: number;
  tender_id: number;
  tender_code: string;
  product_id: number;
  product_name: string;
  npc_supplier_id: number;
  npc_name: string;
  quantity_kg: string;
  unit_price_per_ton: string;
  unit_price_per_kg: string;
  freight_included: boolean;
  delivery_minutes: number;
  status: string;
  accepted_at_seconds: string;
  carrier_id: number | null;
  carrier_name: string | null;
  carrier_price_per_ton: string | null;
  carrier_assigned_at_seconds: string | null;
  delivery_due_at_seconds: string | null;
  delivered_at_seconds: string | null;
  remaining_seconds: string | null;
  landed_cost_tl: string | null;
}

export interface StockMetricItem {
  product_id: number;
  product_code?: string;
  product_name: string;
  stock_kg: string;
  avg_cost_per_kg: string;
  last_purchase_unit_price?: string;
  value_tl: string;
}

export interface StockMetrics {
  items: StockMetricItem[];
  total_stock_kg: string;
  total_value_tl: string;
  total_avg_cost_per_kg: string;
  total_loss_kg: string;
  total_loss_tl: string;
}

export interface HistoryPoint {
  elapsed_seconds: string;
  total_stock_kg: string;
  total_value_tl: string;
  total_avg_cost_per_kg: string;
  products: StockMetricItem[];
}

export interface PurchaseStatsItem {
  product_id: number;
  product_code: string;
  product_name: string;
  purchase_count: number;
  last_unit_price: string;
  min_unit_price: string | null;
  max_unit_price: string | null;
  avg_unit_price: string | null;
}

export interface BudgetState {
  monthly_limit_tl: string;
  spent_tl: string;
  remaining_tl: string;
  usage_percent: string;
  period_index: number;
  period_start_seconds: string;
  period_end_seconds: string;
  exceeded: boolean;
}

export interface ChartSeries {
  id: string;
  label: string;
  color: string;
  dash: string;
  marker: 'circle' | 'square' | 'triangle';
  values: number[];
}

