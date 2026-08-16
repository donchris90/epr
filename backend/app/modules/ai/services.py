"""
Module 25 — AI Construction Assistant (Code: AI)
Service layer. See the SCOPE NOTE in models.py for what is and isn't
implemented for real in this pass -- no LLM is configured in this
environment, so this file implements the grounded data-retrieval TOOLS
(AI-12's own description of the right mechanism), the audit log those
tools write to (AI-13), and the two business rules, all for real.

Business rules encoded here (SRS 4.25):
  - Any figure feeding a financial/contractual document must cite its
    source; generate_report refuses to create a report with an
    uncited figure.
  - Document extraction never auto-commits; commit_extraction refuses
    to run unless the job is already in "reviewed" status.
"""
from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.utils.errors import APIError
from app.modules.ai.models import AIQueryLog, AIGeneratedReport, AIDocumentExtractionJob


def _log_tool_call(tenant_id, *, user_id, tool_name, query_params, context_retrieved):
    """AI-13: every tool invocation is logged with the EXACT context
    retrieved, not a summary of it -- so an auditor can later see
    precisely what data backed a given answer."""
    log = AIQueryLog(
        tenant_id=tenant_id,
        user_id=user_id,
        tool_name=tool_name,
        query_params=query_params,
        context_retrieved=context_retrieved,
        queried_at=datetime.now(timezone.utc),
    )
    db.session.add(log)
    db.session.commit()
    return log


# --- Tools (AI-01, AI-02, AI-03 grounding) ---------------------------------------

def tool_list_at_risk_projects(tenant_id, *, user_id, threshold=0.9):
    """AI-01 grounding: "which project is likely to exceed budget" is
    answered by Module 19's own at-risk computation -- this tool calls
    that real function directly rather than re-deriving the logic."""
    from app.modules.pc import services as pc_services

    threshold_decimal = Decimal(str(threshold))
    snapshots = pc_services.list_at_risk_projects(tenant_id, threshold=threshold_decimal)

    context = [
        {"project_id": str(s.project_id), "period_end": s.period_end.isoformat(), "cpi": str(s.cpi) if s.cpi else None, "spi": str(s.spi) if s.spi else None}
        for s in snapshots
    ]
    _log_tool_call(tenant_id, user_id=user_id, tool_name="list_at_risk_projects", query_params={"threshold": str(threshold)}, context_retrieved=context)
    return context


def tool_list_idle_equipment(tenant_id, *, user_id, period_start, period_end):
    """AI-02 grounding (EQP-11): equipment with zero recorded operated
    hours across the period, from Module 9's real utilization data."""
    from app.modules.eqp.models import Equipment, UtilizationRecord

    rows = (
        db.session.query(Equipment.id, Equipment.name, db.func.coalesce(db.func.sum(UtilizationRecord.hours_operated), 0))
        .outerjoin(
            UtilizationRecord,
            db.and_(
                UtilizationRecord.equipment_id == Equipment.id,
                UtilizationRecord.record_date >= period_start,
                UtilizationRecord.record_date <= period_end,
            ),
        )
        .filter(Equipment.tenant_id == tenant_id)
        .group_by(Equipment.id, Equipment.name)
        .having(db.func.coalesce(db.func.sum(UtilizationRecord.hours_operated), 0) == 0)
        .all()
    )

    context = [{"equipment_id": str(eq_id), "name": name} for eq_id, name, _ in rows]
    _log_tool_call(
        tenant_id, user_id=user_id, tool_name="list_idle_equipment",
        query_params={"period_start": str(period_start), "period_end": str(period_end)}, context_retrieved=context,
    )
    return context


def tool_explain_project_delay(tenant_id, *, user_id, project_id):
    """AI-03 grounding: combines Module 5's real delay events with
    Module 19's real schedule variance for the project -- both fetched
    fresh, not inferred."""
    from app.modules.pln.models import DelayEvent
    from app.modules.pc.models import EVMSnapshot

    delay_events = DelayEvent.query.filter_by(tenant_id=tenant_id, project_id=project_id).all()

    latest_snapshot = (
        EVMSnapshot.query.filter_by(tenant_id=tenant_id, project_id=project_id)
        .order_by(EVMSnapshot.period_end.desc())
        .first()
    )

    context = {
        "delay_events": [
            {"id": str(e.id), "description": getattr(e, "description", None), "delay_days": getattr(e, "delay_days", None)}
            for e in delay_events
        ],
        "latest_schedule_variance": str(latest_snapshot.schedule_variance) if latest_snapshot else None,
        "latest_spi": str(latest_snapshot.spi) if latest_snapshot and latest_snapshot.spi else None,
    }
    _log_tool_call(
        tenant_id, user_id=user_id, tool_name="explain_project_delay",
        query_params={"project_id": str(project_id)}, context_retrieved=context,
    )
    return context


# --- Report generation (AI-04, AI-05, business rule) -----------------------------

def generate_report(tenant_id, *, report_type, content, source_citations, generated_by):
    """
    Business rule: every key in `content` that represents a figure
    (i.e. every key, since this module doesn't accept free-text-only
    reports without at least the figures behind them) must have a
    matching entry in `source_citations`. A report with an uncited
    figure is refused outright -- there is no "generate now, cite
    later" path.
    """
    if not source_citations:
        raise APIError("A report cannot be generated without source citations", status=400)

    missing = [key for key in content if key not in source_citations]
    if missing:
        raise APIError(
            "Every figure in the report must cite its source",
            status=400,
            detail=f"Missing citations for: {', '.join(missing)}",
        )

    for key, citation in source_citations.items():
        if not citation.get("module") or not citation.get("record_id"):
            raise APIError(f"Citation for '{key}' must include both module and record_id", status=400)

    report = AIGeneratedReport(
        tenant_id=tenant_id,
        report_type=report_type,
        content=content,
        source_citations=source_citations,
        generated_by=generated_by,
        generated_at=datetime.now(timezone.utc),
    )
    db.session.add(report)
    db.session.commit()
    return report


# --- Document extraction (AI-06, AI-07, business rule) ---------------------------

def create_extraction_job(tenant_id, *, extraction_type, extracted_data, source_document_id=None, confidence_scores=None, low_confidence_threshold=0.7):
    """
    Represents the OUTCOME of an external document-understanding step
    (OCR/LLM extraction) handing structured data to this module --
    that step itself is out of scope here (see models.py SCOPE NOTE).
    Fields below the confidence threshold are flagged, per AI-06/07's
    explicit requirement to flag low-confidence extractions rather
    than silently guess.
    """
    confidence_scores = confidence_scores or {}
    low_confidence_fields = [field for field, score in confidence_scores.items() if score < low_confidence_threshold]

    job = AIDocumentExtractionJob(
        tenant_id=tenant_id,
        source_document_id=source_document_id,
        extraction_type=extraction_type,
        status="extracted",
        extracted_data=extracted_data,
        confidence_scores=confidence_scores,
        low_confidence_fields=low_confidence_fields,
    )
    db.session.add(job)
    db.session.commit()
    return job


def review_extraction(job: AIDocumentExtractionJob, *, reviewed_by, corrected_data=None):
    """The distinct, explicit human-review step -- required before
    commit_extraction will do anything, regardless of confidence
    scores. Even a 100%-confidence extraction still requires this."""
    if job.status != "extracted":
        raise APIError("Only an extracted (not yet reviewed) job can be reviewed", status=409)

    job.status = "reviewed"
    job.reviewed_by = reviewed_by
    job.reviewed_at = datetime.now(timezone.utc)
    job.corrected_data = corrected_data
    db.session.commit()
    return job


def reject_extraction(job: AIDocumentExtractionJob, *, reviewed_by):
    if job.status not in ("extracted", "reviewed"):
        raise APIError("Job cannot be rejected from its current status", status=409)
    job.status = "rejected"
    job.reviewed_by = reviewed_by
    job.reviewed_at = datetime.now(timezone.utc)
    db.session.commit()
    return job


def commit_extraction_to_boq(job: AIDocumentExtractionJob, *, estimate_version_id, committed_by):
    """
    Business rule: THE only path from extracted data into a real
    Module 3 BOQItem row, and it refuses to run unless the job is
    already "reviewed" -- a status only review_extraction can set,
    which requires its own explicit human action. No confidence score,
    however high, skips this gate.
    """
    if job.status != "reviewed":
        raise APIError("Cannot commit: extraction job has not been reviewed", status=409)
    if job.extraction_type != "boq":
        raise APIError("This commit path is for BOQ extractions only", status=400)

    from app.modules.est.models import BOQItem

    data = {**(job.extracted_data or {}), **(job.corrected_data or {})}  # corrections override raw extraction

    item = BOQItem(
        tenant_id=job.tenant_id,
        estimate_version_id=estimate_version_id,
        item_code=data.get("item_code"),
        description=data.get("description", ""),
        unit=data.get("unit"),
        quantity=data.get("quantity"),
    )
    db.session.add(item)
    db.session.flush()

    job.status = "committed"
    job.committed_record_id = item.id
    job.committed_at = datetime.now(timezone.utc)
    db.session.commit()
    return item
