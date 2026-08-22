// Mirrors backend/app/modules/tbm/schemas.py and models.py -- keep in
// sync by hand when those change.

export type TenderStatus = "draft" | "in_estimate" | "in_approval" | "submitted" | "awarded" | "lost";
export type BidDocumentType = string;
export type BidDocumentStatus = "pending" | "uploaded" | "verified";
export type RFIStatus = "open" | "answered";
export type SubmissionMethod = "portal" | "email" | "hand_delivery" | "courier";
export type ScopeAnnotationType = "inclusion" | "exclusion" | "clarification_needed";
export type ApprovalStepStatus = "pending" | "approved" | "rejected";

export interface Tender {
  id: string;
  opportunity_id: string;
  reference_number: string;
  client_id: string | null;
  consultant_id: string | null;
  submission_deadline: string | null;
  bid_bond_required: boolean;
  bid_bond_amount: string | null;
  tender_fee: string | null;
  currency: string;
  status: TenderStatus;
  is_joint_venture: boolean;
  estimate_locked: boolean;
  reopen_count: number;
  created_at: string;
}

export interface TenderBOQItem {
  id: string;
  tender_id: string;
  parent_id: string | null;
  item_code: string | null;
  description: string;
  unit: string | null;
  quantity: string | null;
  sort_order: number;
}

export interface ScopeItem {
  id: string;
  tender_boq_item_id: string;
  annotation_type: ScopeAnnotationType;
  text: string;
}

export interface BidDocument {
  id: string;
  tender_id: string;
  document_id: string | null;
  doc_type: BidDocumentType;
  status: BidDocumentStatus;
}

export interface RFI {
  id: string;
  tender_id: string;
  related_boq_item_id: string | null;
  question: string;
  due_date: string | null;
  response: string | null;
  status: RFIStatus;
}

export interface Clarification {
  id: string;
  tender_id: string;
  addendum_number: string;
  description: string;
  issued_at: string | null;
  acknowledged: boolean;
  affected_boq_item_ids: string[] | null;
  requires_reestimate: boolean;
}

export interface ApprovalStep {
  id: string;
  tender_id: string;
  step_order: number;
  role_required: string;
  approver_id: string | null;
  status: ApprovalStepStatus;
  comments: string | null;
}

export interface TenderChecklistItem {
  id: string;
  tender_id: string;
  label: string;
  is_mandatory: boolean;
  is_complete: boolean;
}

export interface Submission {
  id: string;
  tender_id: string;
  method: SubmissionMethod;
  submitted_at: string;
  receipt_document_id: string | null;
  acknowledgment_reference: string | null;
}

export interface JVPartner {
  id: string;
  tender_id: string;
  partner_name: string;
  scope_share_pct: string;
  financial_share_pct: string;
}

export interface SubmissionReadiness {
  can_submit: boolean;
  blockers: string[];
}

// --- Tender lifecycle -------------------------------------------------
// Mirrors the ACTUAL enforced transitions in tbm/services.py -- there is
// no generic "status" PATCH endpoint; each of these is its own action
// with its own business rule (see initiate_approval_workflow,
// reopen_for_revision, submit_tender, record_outcome).
export const TENDER_STATUS_LABELS: Record<TenderStatus, string> = {
  draft: "Draft",
  in_estimate: "In Estimate",
  in_approval: "In Approval",
  submitted: "Submitted",
  awarded: "Awarded",
  lost: "Lost",
};
