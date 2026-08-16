// Mirrors backend/app/modules/bdc/schemas.py and models.py -- keep in
// sync by hand when those change. This is the first module in this
// frontend to have real response types rather than `any`; see
// README.md's session notes for the rest of the 25 modules still on
// the untyped pattern this one replaces.

export type LeadStatus = "open" | "converted" | "archived";
export type OpportunityStage = "identified" | "qualified" | "bid_no_bid" | "submitted" | "won" | "lost";

export interface Client {
  id: string;
  name: string;
  billing_address: string | null;
  billing_email: string | null;
  notes: string | null;
  created_at: string;
}

export interface Lead {
  id: string;
  client_id: string | null;
  name: string;
  source: string | null;
  estimated_value: string | null;
  currency: string;
  probability_pct: string | null;
  status: LeadStatus;
  created_at: string;
}

export interface Opportunity {
  id: string;
  lead_id: string | null;
  client_id: string;
  name: string;
  stage: OpportunityStage;
  estimated_value: string | null;
  currency: string;
  submission_deadline: string | null;
  bid_no_bid_decision: string | null;
  contract_id: string | null;
}
