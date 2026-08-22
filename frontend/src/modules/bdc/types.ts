// Mirrors backend/app/modules/bdc/schemas.py and models.py -- keep in
// sync by hand when those change. This is the first module in this
// frontend to have real response types rather than `any`; see
// README.md's session notes for the rest of the 25 modules still on
// the untyped pattern this one replaces.

export type LeadStatus = "open" | "converted" | "archived";
export type OpportunityStage = "identified" | "qualified" | "bid_no_bid" | "submitted" | "won" | "lost";
export type BidNoBidDecision = "bid" | "no_bid";
export type WinLossOutcome = "won" | "lost";

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
  bid_no_bid_decision: BidNoBidDecision | null;
  contract_id: string | null;
  created_at: string;
}

export interface Competitor {
  id: string;
  name: string;
  notes: string | null;
  known_win_count: number;
  known_loss_count: number;
}

export interface Consultant {
  id: string;
  name: string;
  discipline: string | null;
  relationship_notes: string | null;
}

export interface GovernmentAgency {
  id: string;
  name: string;
  jurisdiction: string | null;
  tender_pattern_notes: string | null;
}

export interface WinLossRecord {
  id: string;
  opportunity_id: string;
  outcome: WinLossOutcome;
  winning_price: string | null;
  competitor_id: string | null;
  reason_code: string | null;
  sector: string | null;
  value_band: string | null;
}

export interface WinLossSummaryRow {
  group_key: string;
  group_label: string;
  won: number;
  lost: number;
  total: number;
  win_rate: number;
  won_value: string;
}
