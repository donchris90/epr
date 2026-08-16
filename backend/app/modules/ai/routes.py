"""
Module 25 — AI Construction Assistant (Code: AI)
SRS Section 4.25 — Flask Blueprint. Base path: /v1/ai

See models.py for the scope note: natural-language query parsing and
free-text narrative generation require an LLM this environment doesn't
have configured, so these routes expose the real, structured TOOLS
(AI-12) a natural-language layer would call, plus the audit log,
citation enforcement, and human-review-gate workflows -- all fully real.
"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import envelope

from app.modules.ai import services
from app.modules.ai.models import AIDocumentExtractionJob, AIQueryLog
from app.modules.ai.schemas import (
    AtRiskProjectsQuerySchema,
    IdleEquipmentQuerySchema,
    ExplainDelayQuerySchema,
    GenerateReportSchema,
    ReportSchema,
    CreateExtractionJobSchema,
    ReviewExtractionSchema,
    CommitBOQExtractionSchema,
    ExtractionJobSchema,
)

bp = Blueprint("ai", __name__, url_prefix="/v1/ai")

report_schema = ReportSchema()
job_schema = ExtractionJobSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_job_or_404(job_id) -> AIDocumentExtractionJob:
    j = AIDocumentExtractionJob.query.filter_by(id=job_id, tenant_id=g.tenant_id).first()
    if not j:
        raise APIError("Extraction job not found", status=404)
    return j


@bp.get("/health")
def health():
    return jsonify({"module": "ai", "name": "AI Construction Assistant", "status": "ok"})


# --- Tools (AI-01, AI-02, AI-03, AI-13) --------------------------------------------

@bp.get("/tools/at-risk-projects")
@require_permission("ai:read")
def at_risk_projects():
    args = AtRiskProjectsQuerySchema().load(request.args)
    result = services.tool_list_at_risk_projects(g.tenant_id, user_id=g.user_id, **args)
    return jsonify(envelope(result))


@bp.get("/tools/idle-equipment")
@require_permission("ai:read")
def idle_equipment():
    args = IdleEquipmentQuerySchema().load(request.args)
    result = services.tool_list_idle_equipment(g.tenant_id, user_id=g.user_id, **args)
    return jsonify(envelope(result))


@bp.get("/tools/explain-project-delay")
@require_permission("ai:read")
def explain_project_delay():
    args = ExplainDelayQuerySchema().load(request.args)
    result = services.tool_explain_project_delay(g.tenant_id, user_id=g.user_id, **args)
    return jsonify(result)


@bp.get("/query-logs")
@require_permission("ai:read")
def list_query_logs():
    logs = AIQueryLog.query.filter_by(tenant_id=g.tenant_id).order_by(AIQueryLog.queried_at.desc()).all()
    return jsonify(
        envelope(
            [
                {"id": str(l.id), "tool_name": l.tool_name, "query_params": l.query_params, "queried_at": l.queried_at.isoformat() if l.queried_at else None}
                for l in logs
            ]
        )
    )


# --- Report generation (AI-04, AI-05, business rule) -------------------------------

@bp.post("/reports")
@require_permission("ai:write")
def generate_report():
    data = _load(GenerateReportSchema())
    report = services.generate_report(g.tenant_id, generated_by=g.user_id, **data)
    return jsonify(report_schema.dump(report)), 201


# --- Document extraction (AI-06, AI-07, business rule) ------------------------------

@bp.post("/extraction-jobs")
@require_permission("ai:write")
def create_extraction_job():
    data = _load(CreateExtractionJobSchema())
    job = services.create_extraction_job(g.tenant_id, **data)
    return jsonify(job_schema.dump(job)), 201


@bp.post("/extraction-jobs/<uuid:job_id>/review")
@require_permission("ai:approve")
def review_extraction(job_id):
    job = _get_job_or_404(job_id)
    data = _load(ReviewExtractionSchema())
    job = services.review_extraction(job, reviewed_by=g.user_id, **data)
    return jsonify(job_schema.dump(job))


@bp.post("/extraction-jobs/<uuid:job_id>/reject")
@require_permission("ai:approve")
def reject_extraction(job_id):
    job = _get_job_or_404(job_id)
    job = services.reject_extraction(job, reviewed_by=g.user_id)
    return jsonify(job_schema.dump(job))


@bp.post("/extraction-jobs/<uuid:job_id>/commit-to-boq")
@require_permission("ai:approve")
def commit_extraction_to_boq(job_id):
    job = _get_job_or_404(job_id)
    data = _load(CommitBOQExtractionSchema())
    item = services.commit_extraction_to_boq(job, committed_by=g.user_id, **data)
    return jsonify({"id": str(item.id), "item_code": item.item_code, "description": item.description}), 201
