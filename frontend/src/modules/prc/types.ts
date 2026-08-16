// Mirrors backend/app/modules/prc/schemas.py and models.py -- keep in
// sync by hand when those change. Second module given this treatment
// after BDC; see README.md's session notes for the rest of the
// modules still on the untyped `any` pattern this one replaces.

export type VendorStatus = "active" | "inactive";
export type PRStatus = "draft" | "submitted" | "approved" | "rejected" | "converted";
export type POStatus = "draft" | "pending_approval" | "approved" | "issued" | "closed" | "cancelled";
export type POApprovalStepStatus = "pending" | "approved" | "rejected";
export type MatchStatus = "matched" | "discrepancy";
export type GRNStatus = "draft" | "confirmed";

export interface Vendor {
  id: string;
  name: string;
  tax_registration_number: string | null;
  banking_details: Record<string, unknown> | null;
  categories_supplied: string[] | null;
  status: VendorStatus;
}

export interface PurchaseRequest {
  id: string;
  project_id: string | null;
  cbs_line_item_id: string | null;
  description: string;
  quantity: string;
  unit: string | null;
  estimated_unit_cost: string | null;
  estimated_total: string | null;
  status: PRStatus;
  budget_override: boolean;
}

export interface PurchaseOrderLine {
  id: string;
  purchase_order_id: string;
  material_item_id: string | null;
  description: string;
  quantity: string;
  unit_price: string;
  line_total: string;
  quantity_received: string;
}

export interface PurchaseOrder {
  id: string;
  purchase_request_id: string | null;
  rfq_quotation_id: string | null;
  vendor_id: string;
  po_number: string;
  status: POStatus;
  total_value: string;
  currency: string;
  is_blanket: boolean;
  compliance_waiver: boolean;
}

export interface POApprovalStep {
  id: string;
  step_order: number;
  role_required: string;
  value_threshold: string | null;
  status: POApprovalStepStatus;
  comments: string | null;
}

export interface InvoiceMatch {
  id: string;
  purchase_order_id: string;
  vendor_invoice_reference: string;
  invoice_amount: string;
  po_amount: string;
  grn_amount: string | null;
  match_status: MatchStatus;
  released_for_payment: boolean;
}

// GET /prc/purchase-orders/<id> -- the base PurchaseOrder fields plus
// the extra dumps that route assembles by hand (app/modules/prc/routes.py),
// not a plain PurchaseOrderSchema.dump().
export interface PurchaseOrderDetail extends PurchaseOrder {
  line_items: PurchaseOrderLine[];
  latest_match: InvoiceMatch | null;
  approval_steps: POApprovalStep[];
}

export interface GoodsReceiptNote {
  id: string;
  purchase_order_id: string;
  warehouse_id: string | null;
  received_at: string | null;
  status: GRNStatus;
}
