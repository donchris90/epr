/** Real types matching backend/app/modules/scp/schemas.py and
 * backend/app/modules/sub/schemas.py exactly -- checked directly
 * against the actual Marshmallow schemas and model enums before
 * writing these, not guessed. */

export const AGREEMENT_STATUSES = ["active", "completed", "terminated"] as const;
export type AgreementStatus = (typeof AGREEMENT_STATUSES)[number];

export const CLAIM_TYPES = ["delay", "additional_scope", "other"] as const;
export type ClaimType = (typeof CLAIM_TYPES)[number];

export interface PortalUser {
  id: string;
  subcontractor_id: string;
  email: string;
  is_active: boolean;
}

export interface SubcontractAgreement {
  id: string;
  subcontractor_id: string;
  contract_id: string | null;
  agreement_number: string;
  value: string;
  currency: string;
  payment_terms_summary: string | null;
  retention_percentage: string;
  status: AgreementStatus;
}

export interface ProgressEntry {
  id: string;
  agreement_id: string;
  scope_item_id: string | null;
  submitted_quantity: string;
  submitted_at: string;
  status: string;
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
  status: string;
  issued_at: string;
}

export interface Claim {
  id: string;
  agreement_id: string;
  claim_type: ClaimType;
  description: string;
  claimed_amount: string | null;
  claimed_days: number | null;
  status: string;
  submitted_at: string;
  response_notes: string | null;
}
