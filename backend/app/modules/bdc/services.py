"""
Module 1 — Business Development & CRM (Code: BDC)
Service layer — business logic other modules must call through rather
than querying bdc_* tables directly (SRS Section 3.3).

Encodes the business rules stated in SRS 4.1:
  - An Opportunity cannot transition to "won" without a linked Contract
    record (Module 4).
  - A Bid/No-Bid decision of "No-Bid" closes the opportunity and requires
    a reason code.
  - Only users with the Business Development or Executive role may edit
    scoring criteria weights.
"""
from datetime import datetime, timezone

from app.extensions import db
from app.utils.errors import APIError
from app.modules.bdc.models import (
    Client,
    Contact,
    Lead,
    Opportunity,
    Competitor,
    Consultant,
    GovernmentAgency,
    Proposal,
    WinLossRecord,
    OPPORTUNITY_STAGES,
)


# --- Leads (BDC-01) ----------------------------------------------------

def create_lead(
    tenant_id,
    *,
    name,
    source=None,
    estimated_value=None,
    currency="NGN",
    probability_pct=None,
    client_id=None,
):
    lead = Lead(
        tenant_id=tenant_id,
        name=name,
        source=source,
        estimated_value=estimated_value,
        currency=currency,
        probability_pct=probability_pct,
        client_id=client_id,
    )
    db.session.add(lead)
    db.session.commit()
    return lead


def convert_lead_to_opportunity(lead: Lead, *, client_id: str) -> Opportunity:
    """Creates an Opportunity from a Lead and marks the Lead converted."""
    if lead.status != "open":
        raise APIError("Lead is not open", status=409, detail=f"Lead status is '{lead.status}'")

    opportunity = Opportunity(
        tenant_id=lead.tenant_id,
        lead_id=lead.id,
        client_id=client_id,
        name=lead.name,
        stage="identified",
        estimated_value=lead.estimated_value,
        currency=lead.currency,
    )
    lead.status = "converted"
    db.session.add(opportunity)
    db.session.commit()
    return opportunity


# --- Opportunity pipeline (BDC-03) --------------------------------------

# Valid forward transitions for the configurable pipeline (BDC-03). A
# tenant that customizes stage *names* would customize this map too; the
# underlying stage set stays as defined in models.OPPORTUNITY_STAGES for
# v1 (SRS flags full per-tenant stage configuration as a later concern).
_ALLOWED_TRANSITIONS = {
    "identified": {"qualified", "lost"},
    "qualified": {"bid_no_bid", "lost"},
    "bid_no_bid": {"submitted", "lost"},  # "lost" here covers a "no-bid" close-out
    "submitted": {"won", "lost"},
    "won": set(),
    "lost": set(),
}


def transition_stage(opportunity: Opportunity, new_stage: str, *, actor_id=None) -> Opportunity:
    if new_stage not in OPPORTUNITY_STAGES:
        raise APIError("Invalid stage", status=400, detail=f"'{new_stage}' is not a recognized stage")

    allowed = _ALLOWED_TRANSITIONS.get(opportunity.stage, set())
    if new_stage not in allowed:
        raise APIError(
            "Invalid stage transition",
            status=409,
            detail=f"Cannot move from '{opportunity.stage}' to '{new_stage}'",
        )

    # Business rule: an Opportunity cannot transition to "won" without a
    # linked Contract record (Module 4). Module 4 doesn't exist yet in
    # this scaffold, so this is enforced defensively for when it does.
    if new_stage == "won" and not opportunity.contract_id:
        raise APIError(
            "Cannot mark opportunity as won",
            status=409,
            detail="A linked Contract record (Module 4) is required before marking an Opportunity 'won'.",
        )

    opportunity.stage = new_stage
    opportunity.updated_by = actor_id
    db.session.commit()
    return opportunity


# --- Bid/No-Bid decision workflow (BDC-05) ------------------------------

def record_bid_no_bid_decision(
    opportunity: Opportunity,
    *,
    decision: str,
    scorecard: dict,
    rationale: str,
    approver_id: str,
    reason_code: str = None,
):
    """
    Business rule: a "no_bid" decision closes the opportunity and
    requires a reason code.
    """
    if opportunity.stage != "bid_no_bid":
        raise APIError(
            "Opportunity is not in Bid/No-Bid stage",
            status=409,
            detail=f"Current stage is '{opportunity.stage}'",
        )

    if decision == "no_bid" and not reason_code:
        raise APIError("Reason code required", status=400, detail="A 'No-Bid' decision requires a reason code.")

    opportunity.bid_no_bid_decision = decision
    opportunity.bid_no_bid_scorecard = scorecard
    opportunity.bid_no_bid_rationale = rationale
    opportunity.bid_no_bid_approver_id = approver_id
    opportunity.bid_no_bid_decided_at = datetime.now(timezone.utc)

    if decision == "no_bid":
        opportunity.no_bid_reason_code = reason_code
        opportunity.stage = "lost"

    db.session.commit()
    return opportunity


def assert_can_edit_scoring_weights(user_permissions: list) -> None:
    """Only Business Development or Executive roles may edit scoring
    criteria weights (SRS 4.1 business rule). Callers pass the resolved
    permission list from the JWT (see app/utils/decorators.require_permission)."""
    allowed = {"business_development:configure", "executive:configure", "*"}
    if not allowed.intersection(user_permissions):
        raise APIError("Forbidden", status=403, detail="Only Business Development or Executive roles may edit scoring weights.")


# --- Win/Loss analysis (BDC-10, BDC-11) ---------------------------------

def record_win_loss(
    opportunity: Opportunity,
    *,
    outcome: str,
    winning_price=None,
    competitor_id=None,
    reason_code=None,
    sector=None,
    value_band=None,
):
    if outcome not in ("won", "lost"):
        raise APIError("Invalid outcome", status=400)

    record = WinLossRecord(
        tenant_id=opportunity.tenant_id,
        opportunity_id=opportunity.id,
        outcome=outcome,
        winning_price=winning_price,
        competitor_id=competitor_id,
        reason_code=reason_code,
        sector=sector,
        value_band=value_band,
    )
    db.session.add(record)

    if competitor_id:
        competitor = Competitor.query.get(competitor_id)
        if competitor:
            if outcome == "won":
                # "won" here means the opportunity's own outcome; the
                # named competitor therefore lost this one.
                competitor.known_loss_count += 1
            else:
                competitor.known_win_count += 1

    db.session.commit()
    return record


def link_contract_and_mark_won(opportunity: Opportunity, *, contract_id, actor_id=None) -> Opportunity:
    """
    Called by Module 4 (Contract Management) once a Contract has been
    created for this Opportunity's Tender -- this is what actually
    closes the loop the "won" transition's business rule refers to
    (see transition_stage above). CTM calls this rather than BDC
    reaching into ctm_* tables, keeping the dependency direction
    Module 4 -> Module 1, which matches the SRS's own module numbering
    (a later module may call an earlier one's service, not the reverse).
    """
    if opportunity.contract_id:
        raise APIError(
            "Opportunity already has a linked contract",
            status=409,
            detail=f"Existing contract_id: {opportunity.contract_id}",
        )
    opportunity.contract_id = contract_id
    db.session.commit()
    return transition_stage(opportunity, "won", actor_id=actor_id)


def win_loss_summary(tenant_id, *, group_by="client"):
    """BDC-11: Win/Loss reports summarizing conversion rate by client,
    sector, and value band."""
    # TODO: implement aggregate query once the query/reporting layer
    # (shared across modules) is in place; grouping key is one of
    # "client", "sector", "value_band".
    raise NotImplementedError


# --- Tender calendar deadline notifications (BDC-12) --------------------

def upcoming_deadline_opportunities(tenant_id, *, within_days=(14, 7, 2)):
    """BDC-12: opportunities whose submission_deadline falls on one of the
    configured lead-time thresholds, for the notification scheduler
    (Celery beat task) to pick up."""
    now = datetime.now(timezone.utc)
    results = {}
    for days in within_days:
        window_start = now
        window_end = now.fromtimestamp(now.timestamp() + days * 86400)
        results[days] = (
            Opportunity.query.filter(
                Opportunity.tenant_id == tenant_id,
                Opportunity.submission_deadline.isnot(None),
                Opportunity.submission_deadline.between(window_start, window_end),
                Opportunity.stage.notin_(("won", "lost")),
            ).all()
        )
    return results
