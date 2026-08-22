// Mirrors backend/app/modules/est/schemas.py and models.py -- keep in
// sync by hand when those change.

export type EstimateVersionStatus = "draft" | "submitted" | "superseded";
export type RateComponentType = "material" | "labor" | "equipment" | "subcontract";
export type ContingencyKind = "contingency" | "risk_allowance";
export type ContingencyBasis = "percentage" | "fixed";
export type MarkupScope = "whole_tender" | "section" | "item";

export interface EstimateVersion {
  id: string;
  tender_id: string;
  version_number: number;
  label: string | null;
  status: EstimateVersionStatus;
  notes: string | null;
  created_at: string;
}

export interface BOQItem {
  id: string;
  estimate_version_id: string;
  parent_id: string | null;
  source_tender_boq_item_id: string | null;
  item_code: string | null;
  description: string;
  unit: string | null;
  quantity: string | null;
  sort_order: number;
  unit_rate: string | null;
}

export interface RateAnalysisLine {
  id: string;
  component_type: RateComponentType;
  description: string;
  quantity_per_unit: string;
  unit_cost: string;
  line_total: string;
}

export interface RateAnalysis {
  id: string;
  boq_item_id: string;
  lines: RateAnalysisLine[];
}

export interface CostLibraryItem {
  id: string;
  code: string;
  description: string;
  component_type: RateComponentType;
  unit: string | null;
  default_unit_cost: string;
}

export interface MaterialPrice {
  id: string;
  cost_library_item_id: string | null;
  material_name: string;
  location: string | null;
  unit: string | null;
  price: string;
  effective_date: string;
}

export interface EquipmentRate {
  id: string;
  equipment_type: string;
  source: "owned" | "rental";
  cost_per_hour: string;
  effective_date: string | null;
}

export interface LaborRate {
  id: string;
  trade: string;
  grade: string | null;
  hourly_rate: string;
  statutory_oncost_pct: string;
}

export interface VendorQuotation {
  id: string;
  boq_item_id: string | null;
  vendor_name: string;
  description: string | null;
  quoted_price: string;
  quoted_at: string | null;
  valid_until: string | null;
  is_accepted: boolean;
}

export interface Markup {
  id: string;
  estimate_version_id: string;
  scope: MarkupScope;
  target_boq_item_id: string | null;
  overhead_pct: string;
  profit_pct: string;
}

export interface ContingencyItem {
  id: string;
  estimate_version_id: string;
  kind: ContingencyKind;
  description: string | null;
  basis: ContingencyBasis;
  value: string;
}

export interface EngineersEstimate {
  estimate_version_id: string;
  cost_only_total: string;
}

export interface TenderPriceLineItem {
  boq_item_id: string;
  description: string;
  quantity: string;
  unit_rate: string;
  amount: string;
}

export interface TenderPriceSummary {
  line_items: TenderPriceLineItem[];
  items_total: string;
  contingency_total: string;
  grand_total: string;
}

export interface CBSLineItem {
  id: string;
  cbs_id: string;
  source_boq_item_id: string;
  description: string;
  unit: string | null;
  quantity: string;
  unit_rate: string;
  budgeted_amount: string;
}

export interface CostBreakdownStructure {
  id: string;
  project_id: string | null;
  source_estimate_version_id: string;
  is_approved: boolean;
  approved_at: string | null;
  line_items: CBSLineItem[];
}

export interface BudgetRevision {
  id: string;
  cbs_line_item_id: string;
  reason: string;
  revised_amount: string;
  previous_amount: string;
  status: "pending" | "approved" | "rejected";
}
