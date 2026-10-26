export interface PortalSession {
  id: string; // scp_portal_users.id
  subcontractor_id: string;
  email?: string;
}

export interface Subcontractor {
  id: string;
  name: string;
  trade_specialty?: string | null;
  status: string;
}

export interface Agreement {
  id: string;
  subcontractor_id: string;
  contract_id?: string | null;
  agreement_number: string;
  value: string;
  currency: string;
  payment_terms_summary?: string | null;
  retention_percentage: string;
  status: "active" | "completed" | "terminated" | string;
}

export interface ScopeItem {
  id: string;
  agreement_id: string;
  description: string;
  is_lump_sum: boolean;
  quantity?: string | null;
  unit?: string | null;
  rate?: string | null;
  lump_sum_amount?: string | null;
}

export interface ProgressEntry {
  id: string;
  agreement_id: string;
  scope_item_id?: string | null;
  submitted_quantity: string;
  submitted_at: string;
  status: "submitted" | "verified" | "rejected" | string;
}

export interface PaymentCertificate {
  id: string;
  agreement_id: string;
  certificate_number: string;
  period_start: string;
  period_end: string;
  gross_certified_amount: string;
  retention_withheld: string;
  back_charges_total: string;
  net_payable: string;
  status: "draft" | "issued" | string;
  issued_at?: string | null;
}

export const CLAIM_TYPES = ["delay", "additional_scope", "other"] as const;
export type ClaimType = (typeof CLAIM_TYPES)[number];

export interface Claim {
  id: string;
  agreement_id: string;
  claim_type: ClaimType | string;
  description: string;
  claimed_amount?: string | null;
  claimed_days?: number | null;
  status: "submitted" | "under_review" | "approved" | "rejected" | string;
  submitted_at: string;
  response_notes?: string | null;
}
