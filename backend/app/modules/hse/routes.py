"""
Module 14 — Health, Safety & Environment (HSE) (Code: HSE)
SRS Section 4.14 — Flask Blueprint. Base path: /v1/hse
"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.extensions import db
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import envelope

from app.modules.hse import services
from app.modules.hse.models import (
    RiskAssessment,
    PermitToWork,
    Incident,
    NearMiss,
    ToolboxTalk,
    ToolboxTalkAttendee,
    PPERecord,
    SafetyAudit,
    EnvironmentalMonitoringRecord,
    WasteDisposalRecord,
    EmergencyResponsePlan,
)
from app.modules.hse.schemas import (
    RiskAssessmentSchema,
    IssuePermitSchema,
    ActivatePermitSchema,
    PermitToWorkSchema,
    IncidentInputSchema,
    IncidentSchema,
    NearMissInputSchema,
    NearMissSchema,
    ToolboxTalkInputSchema,
    ToolboxTalkAttendeeInputSchema,
    ToolboxTalkSchema,
    PPERecordInputSchema,
    PPERecordSchema,
    SafetyAuditInputSchema,
    SafetyAuditSchema,
    EnvironmentalMonitoringInputSchema,
    EnvironmentalMonitoringSchema,
    WasteDisposalInputSchema,
    WasteDisposalSchema,
    EmergencyResponsePlanInputSchema,
    EmergencyResponsePlanSchema,
    SafetyIndicatorsQuerySchema,
)

bp = Blueprint("hse", __name__, url_prefix="/v1/hse")

risk_schema = RiskAssessmentSchema()
permit_schema = PermitToWorkSchema()
incident_schema = IncidentSchema()
near_miss_schema = NearMissSchema()
talk_schema = ToolboxTalkSchema()
ppe_schema = PPERecordSchema()
audit_schema = SafetyAuditSchema()
env_schema = EnvironmentalMonitoringSchema()
waste_schema = WasteDisposalSchema()
erp_schema = EmergencyResponsePlanSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_permit_or_404(permit_id) -> PermitToWork:
    p = PermitToWork.query.filter_by(id=permit_id, tenant_id=g.tenant_id).first()
    if not p:
        raise APIError("Permit to Work not found", status=404)
    return p


def _get_incident_or_404(incident_id) -> Incident:
    i = Incident.query.filter_by(id=incident_id, tenant_id=g.tenant_id).first()
    if not i:
        raise APIError("Incident not found", status=404)
    return i


@bp.get("/health")
def health():
    return jsonify({"module": "hse", "name": "Health, Safety & Environment", "status": "ok"})


# --- Risk assessments (HSE-07) ------------------------------------------------

@bp.post("/risk-assessments")
@require_permission("hse:write")
def create_risk_assessment():
    data = _load(risk_schema)
    ra = RiskAssessment(tenant_id=g.tenant_id, **data)
    db.session.add(ra)
    db.session.commit()
    return jsonify(risk_schema.dump(ra)), 201


@bp.get("/risk-assessments")
@require_permission("hse:read")
def list_risk_assessments():
    items = RiskAssessment.query.filter_by(tenant_id=g.tenant_id).all()
    return jsonify(envelope(risk_schema.dump(items, many=True)))


# --- Permit to Work (HSE-01, HSE-12, business rules) --------------------------

@bp.post("/permits")
@require_permission("hse:write")
def issue_permit():
    data = _load(IssuePermitSchema())
    permit = services.issue_permit_to_work(g.tenant_id, actor_id=g.user_id, **data)
    return jsonify(permit_schema.dump(permit)), 201


@bp.post("/permits/<uuid:permit_id>/finalize-approval")
@require_permission("hse:write")
def finalize_permit_approval(permit_id):
    """Marks a draft permit approved once its governing workflow
    instance reports approved -- see services.py:finalize_permit_approval."""
    permit = _get_permit_or_404(permit_id)
    permit = services.finalize_permit_approval(permit, actor_id=g.user_id)
    return jsonify(permit_schema.dump(permit))


@bp.get("/permits")
@require_permission("hse:read")
def list_permits():
    status = request.args.get("status")
    query = PermitToWork.query.filter_by(tenant_id=g.tenant_id)
    if status:
        query = query.filter_by(status=status)
    permits = query.all()
    return jsonify(envelope(permit_schema.dump(permits, many=True)))


@bp.post("/permits/<uuid:permit_id>/activate")
@require_permission("hse:approve")
def activate_permit(permit_id):
    permit = _get_permit_or_404(permit_id)
    data = _load(ActivatePermitSchema())
    permit = services.activate_permit(permit, **data)
    return jsonify(permit_schema.dump(permit))


@bp.post("/permits/<uuid:permit_id>/close")
@require_permission("hse:approve")
def close_permit(permit_id):
    permit = _get_permit_or_404(permit_id)
    permit = services.close_permit(permit, closed_by=g.user_id)
    return jsonify(permit_schema.dump(permit))


@bp.get("/permits/<uuid:permit_id>/is-work-completable")
@require_permission("hse:read")
def is_work_completable(permit_id):
    """The check a caller (e.g. Module 6) should make before marking
    associated work complete."""
    permit = _get_permit_or_404(permit_id)
    return jsonify({"is_work_completable": services.is_work_completable(permit)})


# --- Incidents (HSE-02, business rule) -----------------------------------------

@bp.post("/incidents")
@require_permission("hse:write")
def record_incident():
    data = _load(IncidentInputSchema())
    incident = services.record_incident(g.tenant_id, reported_by=g.user_id, **data)
    return jsonify(incident_schema.dump(incident)), 201


@bp.get("/incidents")
@require_permission("hse:read")
def list_incidents():
    status = request.args.get("status")
    query = Incident.query.filter_by(tenant_id=g.tenant_id)
    if status:
        query = query.filter_by(status=status)
    incidents = query.all()
    return jsonify(envelope(incident_schema.dump(incidents, many=True)))


@bp.post("/incidents/<uuid:incident_id>/close")
@require_permission("hse:officer")
def close_incident(incident_id):
    """Business rule: closure requires HSE Officer sign-off specifically
    -- the `hse:officer` permission is a distinct grant from ordinary
    `hse:write`/`hse:approve`, the same field-level-gate pattern used
    for WFM's medical records. Someone with broad HSE access but not
    this specific grant cannot close an incident, regardless of who
    raised it."""
    incident = _get_incident_or_404(incident_id)
    incident = services.close_incident(incident, hse_officer_id=g.user_id)
    return jsonify(incident_schema.dump(incident))


# --- Near misses (HSE-03) -------------------------------------------------------

@bp.post("/near-misses")
@require_permission("hse:write")
def record_near_miss():
    from datetime import datetime, timezone

    data = _load(NearMissInputSchema())
    near_miss = NearMiss(tenant_id=g.tenant_id, reported_by=g.user_id, occurred_at=data.pop("occurred_at", None) or datetime.now(timezone.utc), **data)
    db.session.add(near_miss)
    db.session.commit()
    return jsonify(near_miss_schema.dump(near_miss)), 201


@bp.get("/near-misses")
@require_permission("hse:read")
def list_near_misses():
    project_id = request.args.get("project_id")
    query = NearMiss.query.filter_by(tenant_id=g.tenant_id)
    if project_id:
        query = query.filter_by(project_id=project_id)
    near_misses = query.all()
    return jsonify(envelope(near_miss_schema.dump(near_misses, many=True)))


# --- Toolbox talks (HSE-04) -------------------------------------------------------

@bp.post("/toolbox-talks")
@require_permission("hse:write")
def create_toolbox_talk():
    data = _load(ToolboxTalkInputSchema())
    talk = ToolboxTalk(tenant_id=g.tenant_id, **data)
    db.session.add(talk)
    db.session.commit()
    return jsonify(talk_schema.dump(talk)), 201


@bp.get("/toolbox-talks")
@require_permission("hse:read")
def list_toolbox_talks():
    project_id = request.args.get("project_id")
    query = ToolboxTalk.query.filter_by(tenant_id=g.tenant_id)
    if project_id:
        query = query.filter_by(project_id=project_id)
    talks = query.all()
    return jsonify(envelope(talk_schema.dump(talks, many=True)))


@bp.post("/toolbox-talks/<uuid:talk_id>/attendees")
@require_permission("hse:write")
def add_toolbox_talk_attendee(talk_id):
    talk = ToolboxTalk.query.filter_by(id=talk_id, tenant_id=g.tenant_id).first()
    if not talk:
        raise APIError("Toolbox talk not found", status=404)

    data = _load(ToolboxTalkAttendeeInputSchema())
    if bool(data.get("employee_id")) == bool(data.get("casual_worker_id")):
        raise APIError("Exactly one of employee_id or casual_worker_id is required", status=400)

    attendee = ToolboxTalkAttendee(tenant_id=g.tenant_id, talk_id=talk.id, **data)
    db.session.add(attendee)
    db.session.commit()
    return jsonify({"id": str(attendee.id)}), 201


@bp.post("/toolbox-talks/<uuid:talk_id>/sign")
@require_permission("hse:write")
def sign_toolbox_talk(talk_id):
    talk = ToolboxTalk.query.filter_by(id=talk_id, tenant_id=g.tenant_id).first()
    if not talk:
        raise APIError("Toolbox talk not found", status=404)
    talk.facilitator_signed = True
    db.session.commit()
    return jsonify(talk_schema.dump(talk))


# --- PPE records (HSE-05) ---------------------------------------------------------

@bp.post("/ppe-records")
@require_permission("hse:write")
def create_ppe_record():
    data = _load(PPERecordInputSchema())
    if bool(data.get("employee_id")) == bool(data.get("casual_worker_id")):
        raise APIError("Exactly one of employee_id or casual_worker_id is required", status=400)

    record = PPERecord(tenant_id=g.tenant_id, **data)
    db.session.add(record)
    db.session.commit()
    return jsonify(ppe_schema.dump(record)), 201


@bp.get("/ppe-records")
@require_permission("hse:read")
def list_ppe_records():
    employee_id = request.args.get("employee_id")
    query = PPERecord.query.filter_by(tenant_id=g.tenant_id)
    if employee_id:
        query = query.filter_by(employee_id=employee_id)
    records = query.all()
    return jsonify(envelope(ppe_schema.dump(records, many=True)))


# --- Safety audits (HSE-06) -------------------------------------------------------

@bp.post("/safety-audits")
@require_permission("hse:write")
def create_safety_audit():
    data = _load(SafetyAuditInputSchema())
    audit = SafetyAudit(tenant_id=g.tenant_id, auditor_id=g.user_id, **data)
    db.session.add(audit)
    db.session.commit()
    return jsonify(audit_schema.dump(audit)), 201


@bp.get("/safety-audits")
@require_permission("hse:read")
def list_safety_audits():
    project_id = request.args.get("project_id")
    query = SafetyAudit.query.filter_by(tenant_id=g.tenant_id)
    if project_id:
        query = query.filter_by(project_id=project_id)
    audits = query.all()
    return jsonify(envelope(audit_schema.dump(audits, many=True)))


# --- Environmental monitoring (HSE-08) ----------------------------------------------

@bp.post("/environmental-monitoring")
@require_permission("hse:write")
def create_environmental_record():
    data = _load(EnvironmentalMonitoringInputSchema())
    value = data.get("value")
    threshold = data.get("threshold")
    exceeds = value is not None and threshold is not None and value > threshold

    record = EnvironmentalMonitoringRecord(tenant_id=g.tenant_id, exceeds_threshold=exceeds, **data)
    db.session.add(record)
    db.session.commit()
    return jsonify(env_schema.dump(record)), 201


@bp.get("/environmental-monitoring")
@require_permission("hse:read")
def list_environmental_records():
    project_id = request.args.get("project_id")
    monitoring_type = request.args.get("monitoring_type")
    query = EnvironmentalMonitoringRecord.query.filter_by(tenant_id=g.tenant_id)
    if project_id:
        query = query.filter_by(project_id=project_id)
    if monitoring_type:
        query = query.filter_by(monitoring_type=monitoring_type)
    records = query.all()
    return jsonify(envelope(env_schema.dump(records, many=True)))


# --- Waste disposal (HSE-09) ----------------------------------------------------------

@bp.post("/waste-disposal")
@require_permission("hse:write")
def create_waste_disposal_record():
    data = _load(WasteDisposalInputSchema())
    record = WasteDisposalRecord(tenant_id=g.tenant_id, **data)
    db.session.add(record)
    db.session.commit()
    return jsonify(waste_schema.dump(record)), 201


@bp.get("/waste-disposal")
@require_permission("hse:read")
def list_waste_disposal_records():
    project_id = request.args.get("project_id")
    query = WasteDisposalRecord.query.filter_by(tenant_id=g.tenant_id)
    if project_id:
        query = query.filter_by(project_id=project_id)
    records = query.all()
    return jsonify(envelope(waste_schema.dump(records, many=True)))


# --- Emergency response plans (HSE-10) ------------------------------------------------

@bp.post("/emergency-response-plans")
@require_permission("hse:approve")
def create_emergency_response_plan():
    data = _load(EmergencyResponsePlanInputSchema())
    plan = EmergencyResponsePlan(tenant_id=g.tenant_id, **data)
    db.session.add(plan)
    db.session.commit()
    return jsonify(erp_schema.dump(plan)), 201


@bp.get("/emergency-response-plans")
@require_permission("hse:read")
def list_emergency_response_plans():
    project_id = request.args.get("project_id")
    query = EmergencyResponsePlan.query.filter_by(tenant_id=g.tenant_id)
    if project_id:
        query = query.filter_by(project_id=project_id)
    plans = query.all()
    return jsonify(envelope(erp_schema.dump(plans, many=True)))


# --- Safety indicators (HSE-11) --------------------------------------------------------

@bp.get("/safety-indicators")
@require_permission("hse:read")
def get_safety_indicators():
    args = SafetyIndicatorsQuerySchema().load(request.args)
    result = services.calculate_safety_indicators(g.tenant_id, **args)
    return jsonify({k: (str(v) if v is not None else None) for k, v in result.items()})
