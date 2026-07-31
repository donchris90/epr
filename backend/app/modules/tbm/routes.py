"""
Module 2 — Tender & Bid Management (Code: TBM)
SRS Section 4.2 — Flask Blueprint. Base path: /v1/tbm
"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.extensions import db
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import get_pagination_params, envelope

from app.modules.tbm import services
from app.modules.tbm.models import (
    Tender,
    TenderBOQItem,
    ScopeItem,
    BidDocument,
    RFI,
    Clarification,
    ApprovalStep,
    TenderChecklistItem,
    JVPartner,
)
from app.modules.tbm.schemas import (
    TenderSchema,
    TenderBOQItemSchema,
    ScopeItemSchema,
    BidDocumentSchema,
    RFISchema,
    RFIResponseSchema,
    ClarificationSchema,
    ApprovalStepSchema,
    InitiateApprovalWorkflowSchema,
    ApprovalDecisionSchema,
    ReopenForRevisionSchema,
    TenderChecklistItemSchema,
    SubmissionSchema,
    JVPartnerSchema,
    TenderOutcomeSchema,
)

bp = Blueprint("tbm", __name__, url_prefix="/v1/tbm")

tender_schema = TenderSchema()
boq_item_schema = TenderBOQItemSchema()
scope_item_schema = ScopeItemSchema()
bid_document_schema = BidDocumentSchema()
rfi_schema = RFISchema()
clarification_schema = ClarificationSchema()
approval_step_schema = ApprovalStepSchema()
checklist_item_schema = TenderChecklistItemSchema()
submission_schema = SubmissionSchema()
jv_partner_schema = JVPartnerSchema()


def _get_tender_or_404(tender_id) -> Tender:
    tender = Tender.query.filter_by(id=tender_id, tenant_id=g.tenant_id, deleted_at=None).first()
    if not tender:
        raise APIError("Tender not found", status=404)
    return tender


def _load(schema, partial=False):
    try:
        return schema.load(request.get_json(force=True) or {}, partial=partial)
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


@bp.get("/health")
def health():
    return jsonify({"module": "tbm", "name": "Tender & Bid Management", "status": "ok"})


# --- Tenders (TBM-01) -----------------------------------------------------

@bp.get("/tenders")
@require_permission("tbm:read")
def list_tenders():
    cursor, limit = get_pagination_params()
    query = Tender.query.filter_by(tenant_id=g.tenant_id, deleted_at=None)
    status = request.args.get("status")
    if status:
        query = query.filter_by(status=status)
    items = query.order_by(Tender.submission_deadline.asc().nullslast()).limit(limit).all()
    return jsonify(envelope(tender_schema.dump(items, many=True)))


@bp.post("/tenders")
@require_permission("tbm:write")
def create_tender():
    data = _load(tender_schema)
    tender = services.create_tender(g.tenant_id, **data)
    return jsonify(tender_schema.dump(tender)), 201


@bp.get("/tenders/<uuid:tender_id>")
@require_permission("tbm:read")
def get_tender(tender_id):
    tender = _get_tender_or_404(tender_id)
    return jsonify(tender_schema.dump(tender))


# --- BOQ import & scope analysis (TBM-02, TBM-03) --------------------------

@bp.post("/tenders/<uuid:tender_id>/boq-items")
@require_permission("tbm:write")
def add_boq_item(tender_id):
    tender = _get_tender_or_404(tender_id)
    data = _load(boq_item_schema)
    item = TenderBOQItem(tenant_id=g.tenant_id, tender_id=tender.id, **data)
    db.session.add(item)
    db.session.commit()
    return jsonify(boq_item_schema.dump(item)), 201


@bp.get("/tenders/<uuid:tender_id>/boq-items")
@require_permission("tbm:read")
def list_boq_items(tender_id):
    _get_tender_or_404(tender_id)
    items = TenderBOQItem.query.filter_by(tender_id=tender_id, tenant_id=g.tenant_id).order_by(
        TenderBOQItem.sort_order
    ).all()
    return jsonify(envelope(boq_item_schema.dump(items, many=True)))


@bp.post("/boq-items/<uuid:boq_item_id>/scope-annotations")
@require_permission("tbm:write")
def add_scope_annotation(boq_item_id):
    boq_item = TenderBOQItem.query.filter_by(id=boq_item_id, tenant_id=g.tenant_id).first()
    if not boq_item:
        raise APIError("BOQ item not found", status=404)

    data = _load(scope_item_schema)
    annotation = ScopeItem(tenant_id=g.tenant_id, tender_boq_item_id=boq_item.id, **data)
    db.session.add(annotation)
    db.session.commit()
    return jsonify(scope_item_schema.dump(annotation)), 201


# --- Bid documents (TBM-04) -------------------------------------------------

@bp.post("/tenders/<uuid:tender_id>/bid-documents")
@require_permission("tbm:write")
def add_bid_document(tender_id):
    tender = _get_tender_or_404(tender_id)
    data = _load(bid_document_schema)
    doc = BidDocument(tenant_id=g.tenant_id, tender_id=tender.id, **data)
    db.session.add(doc)
    db.session.commit()
    return jsonify(bid_document_schema.dump(doc)), 201


@bp.get("/tenders/<uuid:tender_id>/bid-documents")
@require_permission("tbm:read")
def list_bid_documents(tender_id):
    _get_tender_or_404(tender_id)
    items = BidDocument.query.filter_by(tender_id=tender_id, tenant_id=g.tenant_id).all()
    return jsonify(envelope(bid_document_schema.dump(items, many=True)))


# --- RFIs (TBM-05) -----------------------------------------------------------

@bp.post("/tenders/<uuid:tender_id>/rfis")
@require_permission("tbm:write")
def create_rfi(tender_id):
    tender = _get_tender_or_404(tender_id)
    data = _load(rfi_schema)
    rfi = RFI(tenant_id=g.tenant_id, tender_id=tender.id, **data)
    db.session.add(rfi)
    db.session.commit()
    return jsonify(rfi_schema.dump(rfi)), 201


@bp.post("/rfis/<uuid:rfi_id>/respond")
@require_permission("tbm:write")
def respond_to_rfi(rfi_id):
    rfi = RFI.query.filter_by(id=rfi_id, tenant_id=g.tenant_id).first()
    if not rfi:
        raise APIError("RFI not found", status=404)

    from datetime import datetime, timezone

    data = _load(RFIResponseSchema())
    rfi.response = data["response"]
    rfi.status = "answered"
    rfi.responded_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(rfi_schema.dump(rfi))


# --- Clarifications / addenda (TBM-06) ---------------------------------------

@bp.post("/tenders/<uuid:tender_id>/clarifications")
@require_permission("tbm:write")
def add_clarification(tender_id):
    tender = _get_tender_or_404(tender_id)
    data = _load(clarification_schema)
    clarification = Clarification(tenant_id=g.tenant_id, tender_id=tender.id, **data)
    db.session.add(clarification)
    db.session.commit()
    return jsonify(clarification_schema.dump(clarification)), 201


@bp.post("/clarifications/<uuid:clarification_id>/acknowledge")
@require_permission("tbm:write")
def acknowledge_clarification(clarification_id):
    clarification = Clarification.query.filter_by(id=clarification_id, tenant_id=g.tenant_id).first()
    if not clarification:
        raise APIError("Clarification not found", status=404)

    clarification = services.acknowledge_clarification(clarification, actor_id=g.user_id)
    return jsonify(clarification_schema.dump(clarification))


# --- Approval workflow (TBM-07) ------------------------------------------------

@bp.post("/tenders/<uuid:tender_id>/approval-workflow/initiate")
@require_permission("tbm:approve")
def initiate_approval_workflow(tender_id):
    tender = _get_tender_or_404(tender_id)
    data = _load(InitiateApprovalWorkflowSchema())
    tender = services.initiate_approval_workflow(tender, steps=data["steps"])
    return jsonify(tender_schema.dump(tender))


@bp.post("/tenders/<uuid:tender_id>/reopen-for-revision")
@require_permission("tbm:approve")
def reopen_for_revision(tender_id):
    tender = _get_tender_or_404(tender_id)
    data = _load(ReopenForRevisionSchema())
    tender = services.reopen_for_revision(tender, reason=data["reason"], actor_id=g.user_id)
    return jsonify(tender_schema.dump(tender))


@bp.get("/tenders/<uuid:tender_id>/approval-steps")
@require_permission("tbm:read")
def list_approval_steps(tender_id):
    _get_tender_or_404(tender_id)
    steps = ApprovalStep.query.filter_by(tender_id=tender_id, tenant_id=g.tenant_id).order_by(
        ApprovalStep.step_order
    ).all()
    return jsonify(envelope(approval_step_schema.dump(steps, many=True)))


@bp.post("/approval-steps/<uuid:step_id>/decide")
@require_permission("tbm:approve")
def decide_approval_step(step_id):
    step = ApprovalStep.query.filter_by(id=step_id, tenant_id=g.tenant_id).first()
    if not step:
        raise APIError("Approval step not found", status=404)

    data = _load(ApprovalDecisionSchema())
    step = services.decide_approval_step(
        step, decision=data["decision"], approver_id=g.user_id, comments=data.get("comments")
    )
    return jsonify(approval_step_schema.dump(step))


# --- Checklist (TBM-08) ---------------------------------------------------------

@bp.post("/tenders/<uuid:tender_id>/checklist-items")
@require_permission("tbm:write")
def add_checklist_item(tender_id):
    tender = _get_tender_or_404(tender_id)
    data = _load(checklist_item_schema)
    item = TenderChecklistItem(tenant_id=g.tenant_id, tender_id=tender.id, **data)
    db.session.add(item)
    db.session.commit()
    return jsonify(checklist_item_schema.dump(item)), 201


@bp.post("/checklist-items/<uuid:item_id>/complete")
@require_permission("tbm:write")
def complete_checklist_item(item_id):
    from datetime import datetime, timezone

    item = TenderChecklistItem.query.filter_by(id=item_id, tenant_id=g.tenant_id).first()
    if not item:
        raise APIError("Checklist item not found", status=404)

    item.is_complete = True
    item.completed_by = g.user_id
    item.completed_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(checklist_item_schema.dump(item))


# --- Submission (TBM-09, TBM-12) ----------------------------------------------

@bp.get("/tenders/<uuid:tender_id>/submission-readiness")
@require_permission("tbm:read")
def submission_readiness(tender_id):
    tender = _get_tender_or_404(tender_id)
    ok, blockers = services.can_submit(tender)
    return jsonify({"can_submit": ok, "blockers": blockers})


@bp.post("/tenders/<uuid:tender_id>/submit")
@require_permission("tbm:submit")
def submit_tender(tender_id):
    tender = _get_tender_or_404(tender_id)
    data = _load(submission_schema)
    submission = services.record_submission(tender, **data)
    return jsonify(submission_schema.dump(submission)), 201


# --- Win/Loss (TBM-10) ----------------------------------------------------------

@bp.post("/tenders/<uuid:tender_id>/outcome")
@require_permission("tbm:write")
def record_outcome(tender_id):
    tender = _get_tender_or_404(tender_id)
    data = _load(TenderOutcomeSchema())
    outcome = data.pop("outcome")
    record = services.record_tender_outcome(tender, outcome=outcome, **data)
    return jsonify({"tender_status": tender.status, "win_loss_record_id": str(record.id)}), 201


# --- Joint Venture apportionment (TBM-11) --------------------------------------

@bp.post("/tenders/<uuid:tender_id>/jv-partners")
@require_permission("tbm:write")
def add_jv_partner(tender_id):
    tender = _get_tender_or_404(tender_id)
    data = _load(jv_partner_schema)
    partner = JVPartner(tenant_id=g.tenant_id, tender_id=tender.id, **data)
    tender.is_joint_venture = True
    db.session.add(partner)
    db.session.commit()
    return jsonify(jv_partner_schema.dump(partner)), 201


@bp.get("/tenders/<uuid:tender_id>/jv-partners")
@require_permission("tbm:read")
def list_jv_partners(tender_id):
    _get_tender_or_404(tender_id)
    partners = JVPartner.query.filter_by(tender_id=tender_id, tenant_id=g.tenant_id).all()
    return jsonify(envelope(jv_partner_schema.dump(partners, many=True)))
