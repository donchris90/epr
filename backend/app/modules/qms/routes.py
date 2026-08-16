"""
Module 13 — Quality Management (QMS) (Code: QMS)
SRS Section 4.13 — Flask Blueprint. Base path: /v1/qms
"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.extensions import db
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import envelope

from app.modules.qms import services
from app.modules.qms.models import (
    InspectionTestPlan,
    ITPHoldPoint,
    MaterialApproval,
    LabResult,
    NCR,
    CorrectiveAction,
    PunchListItem,
    SnagListItem,
)
from app.modules.qms.schemas import (
    InspectionTestPlanSchema,
    ITPHoldPointInputSchema,
    ITPHoldPointSchema,
    RecordHoldPointResultSchema,
    ApproveConcessionSchema,
    MaterialApprovalInputSchema,
    MaterialApprovalDecisionSchema,
    MaterialApprovalSchema,
    LabResultSchema,
    RecordLabResultOutcomeSchema,
    NCRInputSchema,
    NCRDispositionSchema,
    NCRSchema,
    CorrectiveActionInputSchema,
    CorrectiveActionSchema,
    PunchListItemInputSchema,
    PunchListItemSchema,
    SnagListItemInputSchema,
    SnagListItemSchema,
)

bp = Blueprint("qms", __name__, url_prefix="/v1/qms")

itp_schema = InspectionTestPlanSchema()
hold_point_schema = ITPHoldPointSchema()
material_approval_schema = MaterialApprovalSchema()
lab_result_schema = LabResultSchema()
ncr_schema = NCRSchema()
corrective_action_schema = CorrectiveActionSchema()
punch_list_schema = PunchListItemSchema()
snag_list_schema = SnagListItemSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_itp_or_404(itp_id) -> InspectionTestPlan:
    itp = InspectionTestPlan.query.filter_by(id=itp_id, tenant_id=g.tenant_id).first()
    if not itp:
        raise APIError("Inspection & Test Plan not found", status=404)
    return itp


def _get_hold_point_or_404(hold_point_id) -> ITPHoldPoint:
    hp = ITPHoldPoint.query.filter_by(id=hold_point_id, tenant_id=g.tenant_id).first()
    if not hp:
        raise APIError("Hold point not found", status=404)
    return hp


def _get_ncr_or_404(ncr_id) -> NCR:
    ncr = NCR.query.filter_by(id=ncr_id, tenant_id=g.tenant_id).first()
    if not ncr:
        raise APIError("NCR not found", status=404)
    return ncr


@bp.get("/health")
def health():
    return jsonify({"module": "qms", "name": "Quality Management", "status": "ok"})


# --- Inspection & Test Plans + hold points (QMS-01, business rule) -------------

@bp.post("/itps")
@require_permission("qms:write")
def create_itp():
    data = _load(itp_schema)
    itp = InspectionTestPlan(tenant_id=g.tenant_id, **data)
    db.session.add(itp)
    db.session.commit()
    return jsonify(itp_schema.dump(itp)), 201


@bp.get("/itps")
@require_permission("qms:read")
def list_itps():
    itps = InspectionTestPlan.query.filter_by(tenant_id=g.tenant_id).all()
    return jsonify(envelope(itp_schema.dump(itps, many=True)))


@bp.post("/itps/<uuid:itp_id>/hold-points")
@require_permission("qms:write")
def add_hold_point(itp_id):
    itp = _get_itp_or_404(itp_id)
    data = _load(ITPHoldPointInputSchema())
    hold_point = ITPHoldPoint(tenant_id=g.tenant_id, itp_id=itp.id, **data)
    db.session.add(hold_point)
    db.session.commit()
    return jsonify(hold_point_schema.dump(hold_point)), 201


@bp.get("/itps/<uuid:itp_id>/hold-points")
@require_permission("qms:read")
def list_hold_points(itp_id):
    _get_itp_or_404(itp_id)
    points = ITPHoldPoint.query.filter_by(itp_id=itp_id, tenant_id=g.tenant_id).order_by(ITPHoldPoint.sequence_order).all()
    return jsonify(envelope(hold_point_schema.dump(points, many=True)))


@bp.post("/hold-points/<uuid:hold_point_id>/record-result")
@require_permission("qms:write")
def record_hold_point_result(hold_point_id):
    hold_point = _get_hold_point_or_404(hold_point_id)
    data = _load(RecordHoldPointResultSchema())
    hold_point = services.record_hold_point_result(hold_point, recorded_by=g.user_id, **data)
    return jsonify(hold_point_schema.dump(hold_point))


@bp.post("/hold-points/<uuid:hold_point_id>/approve-concession")
@require_permission("qms:approve")
def approve_concession(hold_point_id):
    hold_point = _get_hold_point_or_404(hold_point_id)
    data = _load(ApproveConcessionSchema())
    hold_point = services.approve_concession(hold_point, reason=data["reason"], approved_by=g.user_id)
    return jsonify(hold_point_schema.dump(hold_point))


@bp.get("/hold-points/<uuid:hold_point_id>/can-proceed")
@require_permission("qms:read")
def can_proceed(hold_point_id):
    """The actual workflow gate check -- callers wiring physical work to
    a hold point should check this before allowing the next step."""
    hold_point = _get_hold_point_or_404(hold_point_id)
    can_go, reason = services.check_can_proceed(hold_point)
    return jsonify({"can_proceed": can_go, "reason": reason})


# --- Material approvals (QMS-02) -----------------------------------------------

@bp.post("/material-approvals")
@require_permission("qms:write")
def create_material_approval():
    data = _load(MaterialApprovalInputSchema())
    approval = MaterialApproval(tenant_id=g.tenant_id, **data)
    db.session.add(approval)
    db.session.commit()
    return jsonify(material_approval_schema.dump(approval)), 201


@bp.post("/material-approvals/<uuid:approval_id>/decide")
@require_permission("qms:approve")
def decide_material_approval(approval_id):
    from datetime import datetime, timezone

    approval = MaterialApproval.query.filter_by(id=approval_id, tenant_id=g.tenant_id).first()
    if not approval:
        raise APIError("Material approval not found", status=404)
    if approval.status != "submitted":
        raise APIError("Material approval already decided", status=409)

    data = _load(MaterialApprovalDecisionSchema())
    approval.status = data["decision"]
    approval.reviewed_by = data.get("reviewed_by")
    approval.review_notes = data.get("review_notes")
    approval.reviewed_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(material_approval_schema.dump(approval))


# --- Lab results (QMS-03) ---------------------------------------------------------

@bp.post("/lab-results")
@require_permission("qms:write")
def create_lab_result():
    data = _load(lab_result_schema)
    result = LabResult(tenant_id=g.tenant_id, **data)
    db.session.add(result)
    db.session.commit()
    return jsonify(lab_result_schema.dump(result)), 201


@bp.post("/lab-results/<uuid:result_id>/record-outcome")
@require_permission("qms:write")
def record_lab_result_outcome(result_id):
    result = LabResult.query.filter_by(id=result_id, tenant_id=g.tenant_id).first()
    if not result:
        raise APIError("Lab result not found", status=404)
    data = _load(RecordLabResultOutcomeSchema())
    result.pass_fail = data["pass_fail"]
    db.session.commit()
    return jsonify(lab_result_schema.dump(result))


# --- NCRs (QMS-04, business rule) --------------------------------------------------

@bp.post("/ncrs")
@require_permission("qms:write")
def create_ncr():
    from datetime import datetime, timezone

    data = _load(NCRInputSchema())
    ncr = NCR(tenant_id=g.tenant_id, raised_by=g.user_id, raised_at=datetime.now(timezone.utc), **data)
    db.session.add(ncr)
    db.session.commit()
    return jsonify(ncr_schema.dump(ncr)), 201


@bp.get("/ncrs")
@require_permission("qms:read")
def list_ncrs():
    status = request.args.get("status")
    query = NCR.query.filter_by(tenant_id=g.tenant_id)
    if status:
        query = query.filter_by(status=status)
    ncrs = query.all()
    return jsonify(envelope(ncr_schema.dump(ncrs, many=True)))


@bp.post("/ncrs/<uuid:ncr_id>/disposition")
@require_permission("qms:approve")
def set_ncr_disposition(ncr_id):
    ncr = _get_ncr_or_404(ncr_id)
    data = _load(NCRDispositionSchema())
    ncr.disposition = data["disposition"]
    db.session.commit()
    return jsonify(ncr_schema.dump(ncr))


@bp.post("/ncrs/<uuid:ncr_id>/close")
@require_permission("qms:approve")
def close_ncr(ncr_id):
    ncr = _get_ncr_or_404(ncr_id)
    ncr = services.close_ncr(ncr, closed_by=g.user_id)
    return jsonify(ncr_schema.dump(ncr))


# --- Corrective actions (QMS-06) ------------------------------------------------------

@bp.post("/corrective-actions")
@require_permission("qms:write")
def create_corrective_action():
    data = _load(CorrectiveActionInputSchema())
    action = CorrectiveAction(tenant_id=g.tenant_id, **data)
    db.session.add(action)
    db.session.commit()
    return jsonify(corrective_action_schema.dump(action)), 201


@bp.post("/corrective-actions/<uuid:action_id>/complete")
@require_permission("qms:write")
def complete_corrective_action(action_id):
    action = CorrectiveAction.query.filter_by(id=action_id, tenant_id=g.tenant_id).first()
    if not action:
        raise APIError("Corrective action not found", status=404)
    action = services.complete_corrective_action(action)
    return jsonify(corrective_action_schema.dump(action))


@bp.post("/corrective-actions/<uuid:action_id>/verify")
@require_permission("qms:approve")
def verify_corrective_action(action_id):
    action = CorrectiveAction.query.filter_by(id=action_id, tenant_id=g.tenant_id).first()
    if not action:
        raise APIError("Corrective action not found", status=404)
    action = services.verify_corrective_action(action, verified_by=g.user_id)
    return jsonify(corrective_action_schema.dump(action))


# --- Punch lists (QMS-05) --------------------------------------------------------------

@bp.post("/punch-list-items")
@require_permission("qms:write")
def create_punch_list_item():
    from datetime import datetime, timezone

    data = _load(PunchListItemInputSchema())
    item = PunchListItem(tenant_id=g.tenant_id, raised_at=datetime.now(timezone.utc), **data)
    db.session.add(item)
    db.session.commit()
    return jsonify(punch_list_schema.dump(item)), 201


@bp.post("/punch-list-items/<uuid:item_id>/close")
@require_permission("qms:write")
def close_punch_list_item(item_id):
    from datetime import datetime, timezone

    item = PunchListItem.query.filter_by(id=item_id, tenant_id=g.tenant_id).first()
    if not item:
        raise APIError("Punch list item not found", status=404)
    if item.status == "closed":
        raise APIError("Punch list item already closed", status=409)
    item.status = "closed"
    item.closed_at = datetime.now(timezone.utc)
    item.closed_by = g.user_id
    db.session.commit()
    return jsonify(punch_list_schema.dump(item))


# --- Snag lists (QMS-07) ----------------------------------------------------------------

@bp.post("/snag-list-items")
@require_permission("qms:write")
def create_snag_list_item():
    from datetime import datetime, timezone

    data = _load(SnagListItemInputSchema())
    item = SnagListItem(tenant_id=g.tenant_id, raised_at=datetime.now(timezone.utc), **data)
    db.session.add(item)
    db.session.commit()
    return jsonify(snag_list_schema.dump(item)), 201


@bp.post("/snag-list-items/<uuid:item_id>/close")
@require_permission("qms:write")
def close_snag_list_item(item_id):
    from datetime import datetime, timezone

    item = SnagListItem.query.filter_by(id=item_id, tenant_id=g.tenant_id).first()
    if not item:
        raise APIError("Snag list item not found", status=404)
    if item.status == "closed":
        raise APIError("Snag list item already closed", status=409)
    item.status = "closed"
    item.closed_at = datetime.now(timezone.utc)
    item.closed_by = g.user_id
    db.session.commit()
    return jsonify(snag_list_schema.dump(item))


# --- Close-out tracking (QMS-08) --------------------------------------------------------

@bp.get("/closeout-readiness")
@require_permission("qms:read")
def closeout_readiness():
    project_id = request.args.get("project_id")
    if not project_id:
        raise APIError("project_id query parameter is required", status=400)
    result = services.check_closeout_readiness(g.tenant_id, project_id=project_id)
    return jsonify(result)
