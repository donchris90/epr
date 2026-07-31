"""
Module 6 — Project Execution (Code: EXE)
Service layer — business logic other modules must call through rather
than querying exe_* tables directly (SRS Section 3.3).

Business rules encoded here (SRS 4.6):
  - A Daily Site Diary, once signed off, becomes read-only. Corrections
    require a linked Amendment record, never an edit to signed content.
  - Work Completed quantities cannot exceed the BOQ item's contracted
    quantity without a linked Variation Order -- this is a WARNING, not
    a hard block, per the SRS's own wording ("triggering a warning if
    exceeded").
"""
from datetime import datetime, timezone

from app.extensions import db
from app.utils.errors import APIError
from app.modules.exe.models import (
    DailySiteDiary,
    DiaryAmendment,
    WorkCompletedRecord,
    SiteIssue,
)


# --- Diary sign-off (EXE-01, EXE-12, business rule) -------------------------

def update_diary(diary: DailySiteDiary, **fields):
    """
    Business rule: a signed diary is read-only. This is the ONLY path
    that should ever write to a diary's own fields (narrative, weather
    summary, workforce counts) -- routes.py must not set attributes
    directly.
    """
    if diary.status == "signed":
        raise APIError(
            "Diary is signed and read-only",
            status=409,
            detail="Use amend_diary to record a correction to a signed diary.",
        )
    for key, value in fields.items():
        setattr(diary, key, value)
    db.session.commit()
    return diary


def sign_diary(diary: DailySiteDiary, *, signed_by):
    if diary.status == "signed":
        raise APIError("Diary is already signed", status=409)

    diary.status = "signed"
    diary.signed_by = signed_by
    diary.signed_at = datetime.now(timezone.utc)
    db.session.commit()
    return diary


def countersign_diary(diary: DailySiteDiary, *, countersigned_by):
    if diary.status != "signed":
        raise APIError("Diary must be signed before it can be countersigned", status=409)
    if diary.countersigned_by:
        raise APIError("Diary is already countersigned", status=409)

    diary.countersigned_by = countersigned_by
    diary.countersigned_at = datetime.now(timezone.utc)
    db.session.commit()
    return diary


def amend_diary(diary: DailySiteDiary, *, description, amended_by):
    """The sanctioned correction path for a signed diary -- allowed
    regardless of sign-off status, since it never mutates the original
    signed content, only adds to the record."""
    amendment = DiaryAmendment(
        tenant_id=diary.tenant_id, diary_id=diary.id, description=description, amended_by=amended_by
    )
    db.session.add(amendment)
    db.session.commit()
    return amendment


# --- Work completed vs. contracted quantity (EXE-06, business rule) --------

def record_work_completed(
    tenant_id,
    *,
    boq_item_id,
    quantity,
    contracted_quantity,
    diary_id=None,
    unit=None,
    recorded_at=None,
    variation_order_id=None,
):
    """
    `contracted_quantity` is supplied by the caller (not looked up here)
    because EXE does not own contract BOQ data -- see the module
    docstring in models.py. Cumulative quantity is computed from this
    module's own WorkCompletedRecord rows, which it does own.
    """
    prior_total = (
        db.session.query(db.func.coalesce(db.func.sum(WorkCompletedRecord.quantity), 0))
        .filter(WorkCompletedRecord.tenant_id == tenant_id, WorkCompletedRecord.boq_item_id == boq_item_id)
        .scalar()
    )
    new_total = prior_total + quantity
    exceeds = new_total > contracted_quantity and not variation_order_id

    record = WorkCompletedRecord(
        tenant_id=tenant_id,
        diary_id=diary_id,
        boq_item_id=boq_item_id,
        quantity=quantity,
        unit=unit,
        recorded_at=recorded_at or datetime.now(timezone.utc),
        variation_order_id=variation_order_id,
        exceeds_contracted_quantity=exceeds,
    )
    db.session.add(record)
    db.session.commit()
    return record


# --- Issue escalation (EXE-07) ------------------------------------------------

def escalate_overdue_issues(tenant_id, *, as_of=None):
    """
    Finds open/in-progress issues past their due date and escalates
    them. Intended to be called by a Celery beat task, but exposed as a
    plain function so it's testable without one (and so a route can
    trigger it on demand during development).
    """
    from datetime import date

    as_of = as_of or date.today()
    overdue = SiteIssue.query.filter(
        SiteIssue.tenant_id == tenant_id,
        SiteIssue.status.in_(("open", "in_progress")),
        SiteIssue.due_date.isnot(None),
        SiteIssue.due_date < as_of,
    ).all()

    for issue in overdue:
        issue.status = "escalated"
        issue.escalated_at = datetime.now(timezone.utc)

    db.session.commit()
    return overdue
