"""
Module 14 — Health, Safety & Environment (HSE) (Code: HSE)
Service layer — business logic other modules must call through rather
than querying hse_* tables directly (SRS Section 3.3).

Business rules encoded here (SRS 4.14):
  - A Permit to Work must be FORMALLY closed (not merely time-expired)
    before associated work is marked complete elsewhere.
  - Every recordable Incident automatically generates a Corrective
    Action requirement, and closure of that action requires sign-off
    by the HSE Officer role specifically, regardless of who raised it
    (the role check is enforced in routes.py via a distinct
    `hse:officer` permission, the same field-level-gate pattern used
    for WFM's medical records).
  - HSE-12: Permit to Work issuance is blocked if the linked Risk
    Assessment is expired or the involved workers' safety training
    isn't current.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.utils.errors import APIError
from app.modules.hse.models import PermitToWork, RiskAssessment, Incident


# --- Permit to Work (HSE-01, HSE-12, business rules) -------------------------

def issue_permit_to_work(
    tenant_id,
    *,
    project_id,
    permit_type,
    risk_assessment_id=None,
    description=None,
    workers_training_current=True,
    as_of=None,
):
    """
    Business rule (HSE-12): blocked if the linked Risk Assessment is
    expired, or the involved workers' safety training isn't current
    (that fact supplied by the caller -- see module docstring).
    """
    as_of = as_of or date.today()

    risk_assessment = None
    if risk_assessment_id:
        risk_assessment = RiskAssessment.query.filter_by(id=risk_assessment_id, tenant_id=tenant_id).first()
        if not risk_assessment:
            raise APIError("Risk assessment not found", status=404)

        expired = risk_assessment.status != "active" or (
            risk_assessment.valid_until is not None and risk_assessment.valid_until < as_of
        )
        if expired:
            raise APIError(
                "Cannot issue permit: linked Risk Assessment is expired or not active",
                status=409,
                detail=f"Risk assessment status='{risk_assessment.status}', valid_until={risk_assessment.valid_until}.",
            )

    if not workers_training_current:
        raise APIError(
            "Cannot issue permit: involved workers' safety training is not current",
            status=409,
        )

    permit = PermitToWork(
        tenant_id=tenant_id,
        project_id=project_id,
        permit_type=permit_type,
        description=description,
        risk_assessment_id=risk_assessment_id,
        status="approved",
        approved_at=datetime.now(timezone.utc),
    )
    db.session.add(permit)
    db.session.commit()
    return permit


def activate_permit(permit: PermitToWork, *, valid_until=None):
    if permit.status != "approved":
        raise APIError("Permit must be approved before it can be activated", status=409)
    permit.status = "active"
    permit.issued_at = datetime.now(timezone.utc)
    permit.valid_until = valid_until
    db.session.commit()
    return permit


def close_permit(permit: PermitToWork, *, closed_by):
    """
    Business rule: this is the ONLY path that sets `formally_closed`.
    A permit whose `valid_until` has simply passed is NOT considered
    closed by this system -- callers checking "is this work permit
    resolved" must check `formally_closed`, never just the time window.
    """
    if permit.status == "closed":
        raise APIError("Permit is already closed", status=409)
    if permit.status != "active":
        raise APIError("Only an active permit can be formally closed", status=409, detail=f"Current status is '{permit.status}'")

    permit.status = "closed"
    permit.formally_closed = True
    permit.closed_at = datetime.now(timezone.utc)
    permit.closed_by = closed_by
    db.session.commit()
    return permit


def is_work_completable(permit: PermitToWork) -> bool:
    """
    The check a caller (e.g. a route in Module 6) should make before
    marking associated work complete -- deliberately checks
    `formally_closed`, not `status == 'closed'` alone and never
    `valid_until`, per the business rule.
    """
    return permit.formally_closed


# --- Incidents (HSE-02, business rule) ----------------------------------------

def record_incident(
    tenant_id, *, classification, description, project_id=None, regulatory_reportable=False, occurred_at=None, reported_by=None
):
    """
    Business rule: every recordable incident automatically generates a
    linked Corrective Action in Module 13 -- a cross-module service
    call (HSE, module 14, calling QMS, module 13 -- an earlier module's
    service, which is the sanctioned direction), not a duplicated table.
    """
    from app.modules.qms.models import CorrectiveAction

    incident = Incident(
        tenant_id=tenant_id,
        project_id=project_id,
        classification=classification,
        description=description,
        regulatory_reportable=regulatory_reportable,
        occurred_at=occurred_at or datetime.now(timezone.utc),
        reported_by=reported_by,
    )
    db.session.add(incident)
    db.session.flush()

    corrective_action = CorrectiveAction(
        tenant_id=tenant_id,
        source="incident",
        description=f"Corrective action required for incident: {description}",
    )
    db.session.add(corrective_action)
    db.session.flush()

    incident.corrective_action_id = corrective_action.id
    db.session.commit()
    return incident


def close_incident(incident: Incident, *, hse_officer_id):
    """
    Business rule: closure requires the linked Corrective Action to be
    verified, and requires HSE Officer sign-off specifically -- the
    `hse:officer` permission gate in routes.py is what actually
    enforces "regardless of who raised it"; this function assumes that
    gate already passed and focuses on the state check.
    """
    from app.modules.qms.models import CorrectiveAction

    if incident.status == "closed":
        raise APIError("Incident is already closed", status=409)

    action = CorrectiveAction.query.filter_by(id=incident.corrective_action_id, tenant_id=incident.tenant_id).first()
    if not action or action.status != "verified":
        raise APIError(
            "Cannot close incident: linked Corrective Action is not verified as complete",
            status=409,
        )

    incident.status = "closed"
    db.session.commit()
    return incident


# --- Safety indicators (HSE-11) ------------------------------------------------

def calculate_safety_indicators(tenant_id, *, project_id=None, period_start, period_end, total_hours_worked):
    """
    TRIR (Total Recordable Incident Rate) = (recordable incidents ×
    200,000) / total hours worked -- the OSHA-standard 200,000 = 100
    full-time workers × 2,000 hours/year, i.e. "per 100 workers per
    year." LTIFR (Lost Time Injury Frequency Rate) = (lost-time
    incidents × 1,000,000) / total hours worked -- the standard "per
    million hours worked" convention. `total_hours_worked` is supplied
    by the caller since HSE does not own Module 6/11's hours data.
    """
    query = Incident.query.filter(
        Incident.tenant_id == tenant_id,
        Incident.occurred_at >= period_start,
        Incident.occurred_at <= period_end,
    )
    if project_id:
        query = query.filter(Incident.project_id == project_id)
    incidents = query.all()

    recordable = [i for i in incidents if i.classification != "first_aid"]
    lost_time = [i for i in incidents if i.classification in ("lost_time", "fatality")]

    from app.modules.hse.models import NearMiss

    near_miss_query = NearMiss.query.filter(
        NearMiss.tenant_id == tenant_id, NearMiss.occurred_at >= period_start, NearMiss.occurred_at <= period_end
    )
    if project_id:
        near_miss_query = near_miss_query.filter(NearMiss.project_id == project_id)
    near_misses = near_miss_query.count()

    hours = Decimal(str(total_hours_worked))
    trir = (Decimal(len(recordable)) * Decimal("200000") / hours) if hours > 0 else None
    ltifr = (Decimal(len(lost_time)) * Decimal("1000000") / hours) if hours > 0 else None
    near_miss_reporting_rate = (
        Decimal(near_misses) / Decimal(len(incidents)) if incidents else None
    )

    return {
        "recordable_incidents": len(recordable),
        "lost_time_incidents": len(lost_time),
        "near_misses": near_misses,
        "total_hours_worked": hours,
        "trir": trir,
        "ltifr": ltifr,
        "near_miss_reporting_rate": near_miss_reporting_rate,
    }
