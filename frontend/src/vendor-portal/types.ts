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
}

export interface InvoiceUpload {
  id: string;
  purchase_order_id: string | null;
  subcontract_certificate_id: string | null;
  invoice_number: string;
  amount: string;
  status: string;
}

export interface BankingChangeRequest {
  id: string;
  vendor_id: string;
  proposed_banking_details: Record<string, string>;
  status: string;
  submitted_at: string;
  reviewed_by: string | null;
  rejection_reason: string | null;
}
