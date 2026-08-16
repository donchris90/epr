"""
Module 2 — Tender & Bid Management (Code: TBM)
Service layer — business logic other modules must call through rather
than querying tbm_* tables directly (SRS Section 3.3).

Business rules encoded here (SRS 4.2):
  - A Tender's estimate (Module 3) is locked from further edits once the
    Bid Approval Workflow is initiated; changes thereafter require an
    explicit "reopen for revision" action logged with a reason.
  - Every addendum received (TBM-06) must be acknowledged before
    submission; the system blocks submission sign-off otherwise.
  - TBM-12: submission sign-off is blocked if any mandatory checklist
    item, RFI response, or approval step is outstanding.
"""
from datetime import datetime, timezone

from app.extensions import db
from app.utils.errors import APIError
from app.modules.tbm.models import (
    Tender,
    ApprovalStep,
    TenderChecklistItem,
    Clarification,
    RFI,
    Submission,
)


# --- Tender registration & estimate lock (TBM-01, business rule) --------

def create_tender(tenant_id, *, opportunity_id, reference_number, **kwargs):
    tender = Tender(tenant_id=tenant_id, opportunity_id=opportunity_id, reference_number=reference_number, **kwargs)
    db.session.add(tender)
    db.session.commit()
    return tender


def initiate_approval_workflow(tender: Tender, *, steps: list):
    """
    Business rule: initiating the approval workflow locks the estimate.
    `steps` is an ordered list of {"role_required": str} dicts.
    """
    if tender.estimate_locked:
        raise APIError(
            "Approval workflow already initiated",
            status=409,
            detail="Estimate is already locked. Use reopen_for_revision to make further changes.",
        )
    if not steps:
        raise APIError("At least one approval step is required", status=400)

    for i, step in enumerate(steps, start=1):
        db.session.add(
            ApprovalStep(
                tenant_id=tender.tenant_id,
                tender_id=tender.id,
                step_order=i,
                role_required=step["role_required"],
            )
        )

    tender.estimate_locked = True
    tender.estimate_locked_at = datetime.now(timezone.utc)
    tender.status = "in_approval"
    db.session.commit()
    return tender


def reopen_for_revision(tender: Tender, *, reason: str, actor_id=None):
    """Business rule: the estimate lock can only be lifted via this
    explicit, reason-logged action -- never by silently editing a
    locked tender."""
    if not tender.estimate_locked:
        raise APIError("Tender estimate is not locked", status=409)
    if not reason:
        raise APIError("A reason is required to reopen a tender for revision", status=400)

    tender.estimate_locked = False
    tender.estimate_locked_at = None
    tender.reopen_count += 1
    tender.last_reopen_reason = reason
    tender.status = "in_estimate"
    tender.updated_by = actor_id

    # Reopening invalidates any in-flight approval decisions -- they must
    # be re-sought once the revised estimate is ready to go around again.
    for step in tender.approval_steps:
        step.status = "pending"
        step.decided_at = None
        step.comments = None

    db.session.commit()
    return tender


# --- Approval workflow (TBM-07) ------------------------------------------

def decide_approval_step(step: ApprovalStep, *, decision: str, approver_id, comments=None):
    if decision not in ("approved", "rejected"):
        raise APIError("Invalid decision", status=400)
    if step.status != "pending":
        raise APIError("Approval step already decided", status=409, detail=f"Current status is '{step.status}'")

    # Enforce sequential approval: this step's predecessors must already
    # be approved (a configurable workflow still implies an order, per
    # the Estimator -> Commercial Manager -> MD example in the SRS).
    earlier_pending = (
        ApprovalStep.query.filter(
            ApprovalStep.tender_id == step.tender_id,
            ApprovalStep.step_order < step.step_order,
            ApprovalStep.status != "approved",
        ).first()
    )
    if earlier_pending:
        raise APIError(
            "Earlier approval step not yet approved",
            status=409,
            detail=f"Step {earlier_pending.step_order} ('{earlier_pending.role_required}') must be approved first.",
        )

    step.status = decision
    step.approver_id = approver_id
    step.comments = comments
    step.decided_at = datetime.now(timezone.utc)
    db.session.commit()
    return step


# --- Clarifications / addenda (TBM-06) ------------------------------------

def acknowledge_clarification(clarification: Clarification, *, actor_id):
    clarification.acknowledged = True
    clarification.acknowledged_at = datetime.now(timezone.utc)
    clarification.acknowledged_by = actor_id
    db.session.commit()
    return clarification


# --- Submission sign-off (TBM-09, TBM-12) ----------------------------------

def _outstanding_submission_blockers(tender: Tender) -> list:
    """Returns a list of human-readable reasons submission is currently
    blocked, per TBM-12. Empty list means submission may proceed."""
    blockers = []

    incomplete_mandatory = [
        item.label
        for item in TenderChecklistItem.query.filter_by(tender_id=tender.id, is_mandatory=True, is_complete=False)
    ]
    if incomplete_mandatory:
        blockers.append(f"Incomplete mandatory checklist items: {', '.join(incomplete_mandatory)}")

    unanswered_rfis = RFI.query.filter(RFI.tender_id == tender.id, RFI.status != "answered").count()
    if unanswered_rfis:
        blockers.append(f"{unanswered_rfis} RFI(s) awaiting a response")

    pending_approvals = ApprovalStep.query.filter(
        ApprovalStep.tender_id == tender.id, ApprovalStep.status != "approved"
    ).count()
    if pending_approvals:
        blockers.append(f"{pending_approvals} approval step(s) not yet approved")

    # Business rule: every addendum must be acknowledged before submission.
    unacknowledged = Clarification.query.filter_by(tender_id=tender.id, acknowledged=False).count()
    if unacknowledged:
        blockers.append(f"{unacknowledged} addendum/addenda not yet acknowledged")

    return blockers


def can_submit(tender: Tender) -> tuple[bool, list]:
    blockers = _outstanding_submission_blockers(tender)
    return (len(blockers) == 0, blockers)


def record_submission(tender: Tender, *, method, submitted_at, receipt_document_id=None, acknowledgment_reference=None):
    ok, blockers = can_submit(tender)
    if not ok:
        raise APIError(
            "Submission blocked",
            status=409,
            detail="; ".join(blockers),
        )
    if tender.submission is not None:
        raise APIError("Tender has already been submitted", status=409)

    submission = Submission(
        tenant_id=tender.tenant_id,
        tender_id=tender.id,
        method=method,
        submitted_at=submitted_at,
        receipt_document_id=receipt_document_id,
        acknowledgment_reference=acknowledgment_reference,
    )
    db.session.add(submission)
    tender.status = "submitted"
    db.session.commit()
    return submission


# --- Win/Loss analysis (TBM-10) -- delegates to BDC, does not duplicate ----

def record_tender_outcome(tender: Tender, *, outcome, **win_loss_kwargs):
    """
    TBM-10: delegates to Module 1's win/loss service against the Tender's
    linked Opportunity, rather than maintaining a second win/loss table
    (bounded-context discipline, SRS Section 3.3).
    """
    from app.modules.bdc.models import Opportunity
    from app.modules.bdc import services as bdc_services

    opportunity = Opportunity.query.filter_by(id=tender.opportunity_id, tenant_id=tender.tenant_id).first()
    if not opportunity:
        raise APIError("Linked opportunity not found", status=409, detail="Tender has no valid linked Opportunity.")

    tender.status = "awarded" if outcome == "won" else "lost"
    db.session.commit()

    return bdc_services.record_win_loss(opportunity, outcome=outcome, **win_loss_kwargs)
