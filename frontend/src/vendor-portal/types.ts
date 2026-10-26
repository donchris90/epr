/** Real types matching backend/app/modules/vnp/schemas.py and
 * backend/app/modules/prc/schemas.py exactly -- checked directly
 * against the actual Marshmallow schemas before writing these, not
 * guessed. */

export interface PortalUser {
  id: string;
  vendor_id: string;
  email: string;
  is_active: boolean;
}

export interface PurchaseOrder {
  id: string;
  purchase_request_id: string | null;
  rfq_quotation_id: string | null;
  vendor_id: string;
  po_number: string;
  status: string;
  total_value: string;
  currency: string;
  is_blanket: boolean;
  compliance_waiver: boolean;
}

export interface OrderAcknowledgment {
  id: string;
  purchase_order_id: string;
  acknowledged_at: string;
  expected_delivery_date: string | null;
}

export interface Quotation {
  id: string;
  rfq_id: string;
  price: string;
  lead_time_days?: number | null;
  payment_terms?: string | null;
  submitted_at?: string | null;
}

export interface RfqInvitation {
  invitation_id: string;
  rfq_id: string;
  title: string;
  description: string | null;
  response_deadline: string | null;
  rfq_status: string;
  invitation_status: string;
  quote: Quotation | null;
  can_quote: boolean;
}

export interface InvoiceUpload {
  id: string;
  purchase_order_id: string | null;
  subcontract_certificate_id: string | null;
  invoice_number: string;
  amount: string;
  status: string;
}

export interface BankingDetails {
  bank_name: string;
  account_name: string;
  account_number: string;
}

export interface BankingChangeRequest {
  id: string;
  vendor_id: string;
  proposed_banking_details: Partial<BankingDetails>;
  status: "pending" | "approved" | "rejected" | string;
  submitted_at: string | null;
  reviewed_at: string | null;
  rejection_reason: string | null;
}
