"""
Module 13 — Quality Management (QMS) (Code: QMS)
Service layer — business logic other modules must call through rather
than querying qms_* tables directly (SRS Section 3.3).

Business rules encoded here (SRS 4.13):
  - Work may not proceed past a defined ITP hold point without a
    recorded pass or an approved concession, enforced as a workflow
    gate (check_can_proceed) rather than a passive reminder.
  - An NCR cannot be closed without a linked Corrective Action verified
    as complete.
"""
from datetime import datetime, timezone

from app.extensions import db
from app.utils.errors import APIError
from app.modules.qms.models import (
    ITPHoldPoint,
    NCR,
    CorrectiveAction,
    PunchListItem,
    SnagListItem,
)


# --- Hold points (QMS-01, business rule) ------------------------------------

def record_hold_point_result(hold_point: ITPHoldPoint, *, passed: bool, recorded_by, inspection_log_id=None):
    if hold_point.status not in ("pending", "failed"):
        raise APIError("Hold point has already been passed or has an approved concession", status=409)

    hold_point.status = "passed" if passed else "failed"
    hold_point.result_recorded_by = recorded_by
    hold_point.result_recorded_at = datetime.now(timezone.utc)
    hold_point.inspection_log_id = inspection_log_id
    db.session.commit()
    return hold_point


def approve_concession(hold_point: ITPHoldPoint, *, reason: str, approved_by):
    """The ONLY other sanctioned way past a failed/pending mandatory
    hold point besides an actual pass -- a recorded, attributable
    exception, not a silent bypass."""
    if hold_point.status == "passed":
        raise APIError("Hold point has already passed; a concession is unnecessary", status=409)
    if hold_point.status == "concession_approved":
        raise APIError("A concession has already been approved for this hold point", status=409)
    if not reason:
        raise APIError("A reason is required to approve a concession", status=400)

    hold_point.status = "concession_approved"
    hold_point.concession_reason = reason
    hold_point.concession_approved_by = approved_by
    hold_point.concession_approved_at = datetime.now(timezone.utc)
    db.session.commit()
    return hold_point


def check_can_proceed(hold_point: ITPHoldPoint):
    """
    The actual workflow gate: callers (e.g. a route in Module 6 wiring
    physical work to a hold point) should call this BEFORE allowing the
    next step of work, not merely display the hold point's status.
    Non-mandatory hold points never block, per is_mandatory_hold.
    Returns (can_proceed: bool, reason: str).
    """
    if not hold_point.is_mandatory_hold:
        return True, "Hold point is advisory, not mandatory"
    if hold_point.status in ("passed", "concession_approved"):
        return True, f"Hold point is {hold_point.status}"
    return False, f"Hold point status is '{hold_point.status}' -- work cannot proceed without a pass or approved concession"


# --- NCRs (QMS-04, business rule) --------------------------------------------

def close_ncr(ncr: NCR, *, closed_by=None):
    """
    Business rule: an NCR cannot be closed without a linked Corrective
    Action verified as complete. "Linked" AND "verified" both matter --
    an NCR with corrective actions still stuck at "completed" (not yet
    "verified") is not closeable either; completing an action and
    someone independently confirming it worked are different states.
    """
    if ncr.status == "closed":
        raise APIError("NCR is already closed", status=409)

    if not ncr.corrective_actions:
        raise APIError(
            "Cannot close NCR without a linked Corrective Action",
            status=409,
            detail="No corrective actions are linked to this NCR.",
        )

    verified = [ca for ca in ncr.corrective_actions if ca.status == "verified"]
    if not verified:
        raise APIError(
            "Cannot close NCR: no linked Corrective Action is verified as complete",
            status=409,
            detail=f"{len(ncr.corrective_actions)} linked action(s), none verified.",
        )

    ncr.status = "closed"
    ncr.closed_at = datetime.now(timezone.utc)
    db.session.commit()
    return ncr


# --- Corrective actions (QMS-06) ----------------------------------------------

def complete_corrective_action(action: CorrectiveAction):
    if action.status != "open":
        raise APIError("Corrective action is not open", status=409)
    action.status = "completed"
    db.session.commit()
    return action


def verify_corrective_action(action: CorrectiveAction, *, verified_by):
    """The distinct verification-of-closure step (QMS-06) -- someone
    OTHER than whoever marked it "completed" confirming it actually
    resolved the issue, before it can back an NCR closure."""
    if action.status != "completed":
        raise APIError("Corrective action must be completed before it can be verified", status=409)

    action.status = "verified"
    action.verified_by = verified_by
    action.verified_at = datetime.now(timezone.utc)
    db.session.commit()
    return action


# --- Close-out tracking (QMS-08) ----------------------------------------------

def check_closeout_readiness(tenant_id, *, project_id):
    """
    QMS-08: all NCRs, punch list items, and snag list items in scope
    must be closed before that scope can be marked complete elsewhere
    (Module 6/19). A read-only gate check -- the actual "mark complete"
    action lives in whichever module owns the scope being closed out.
    """
    open_ncrs = NCR.query.filter_by(tenant_id=tenant_id, project_id=project_id, status="open").count()
    open_punch = PunchListItem.query.filter_by(tenant_id=tenant_id, project_id=project_id, status="open").count()
    open_snags = SnagListItem.query.filter_by(tenant_id=tenant_id, project_id=project_id, status="open").count()

    blockers = []
    if open_ncrs:
        blockers.append(f"{open_ncrs} open NCR(s)")
    if open_punch:
        blockers.append(f"{open_punch} open punch list item(s)")
    if open_snags:
        blockers.append(f"{open_snags} open snag list item(s)")

    return {"can_close_out": len(blockers) == 0, "blockers": blockers}
