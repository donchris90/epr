"""
Module 1 — Business Development & CRM (Code: BDC)
SRS Section 4.1 — Flask Blueprint. Base path: /v1/bdc
"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.extensions import db
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import get_pagination_params, envelope

from app.modules.bdc import services
from app.modules.bdc.models import Client, Lead, Opportunity, Competitor, Consultant, GovernmentAgency
from app.modules.bdc.schemas import (
    ClientSchema,
    LeadSchema,
    OpportunitySchema,
    StageTransitionSchema,
    BidNoBidDecisionSchema,
    WinLossRecordSchema,
    CompetitorSchema,
    ConsultantSchema,
    GovernmentAgencySchema,
)

bp = Blueprint("bdc", __name__, url_prefix="/v1/bdc")

client_schema = ClientSchema()
lead_schema = LeadSchema()
opportunity_schema = OpportunitySchema()


@bp.get("/health")
def health():
    return jsonify({"module": "bdc", "name": "Business Development & CRM", "status": "ok"})


# --- Clients (BDC-02) ---------------------------------------------------

@bp.get("/clients")
@require_permission("bdc:read")
def list_clients():
    cursor, limit = get_pagination_params()
    query = Client.query.filter_by(tenant_id=g.tenant_id, deleted_at=None).order_by(Client.name)
    items = query.limit(limit).all()
    return jsonify(envelope(client_schema.dump(items, many=True)))


@bp.post("/clients")
@require_permission("bdc:write")
def create_client():
    try:
        data = client_schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))

    client = Client(tenant_id=g.tenant_id, **data)
    db.session.add(client)
    db.session.commit()
    return jsonify(client_schema.dump(client)), 201


# --- Leads (BDC-01) ------------------------------------------------------

@bp.get("/leads")
@require_permission("bdc:read")
def list_leads():
    cursor, limit = get_pagination_params()
    query = Lead.query.filter_by(tenant_id=g.tenant_id, deleted_at=None).order_by(Lead.created_at.desc())
    items = query.limit(limit).all()
    return jsonify(envelope(lead_schema.dump(items, many=True)))


@bp.post("/leads")
@require_permission("bdc:write")
def create_lead():
    try:
        data = lead_schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))

    lead = services.create_lead(g.tenant_id, **data)
    return jsonify(lead_schema.dump(lead)), 201


@bp.post("/leads/<uuid:lead_id>/convert")
@require_permission("bdc:write")
def convert_lead(lead_id):
    lead = Lead.query.filter_by(id=lead_id, tenant_id=g.tenant_id).first()
    if not lead:
        raise APIError("Lead not found", status=404)

    body = request.get_json(force=True) or {}
    client_id = body.get("client_id")
    if not client_id:
        raise APIError("client_id is required", status=400)

    opportunity = services.convert_lead_to_opportunity(lead, client_id=client_id)
    return jsonify(opportunity_schema.dump(opportunity)), 201


# --- Opportunities / pipeline (BDC-03, BDC-04) ---------------------------

@bp.get("/opportunities")
@require_permission("bdc:read")
def list_opportunities():
    cursor, limit = get_pagination_params()
    query = Opportunity.query.filter_by(tenant_id=g.tenant_id, deleted_at=None)

    stage = request.args.get("stage")
    if stage:
        query = query.filter_by(stage=stage)

    query = query.order_by(Opportunity.submission_deadline.asc().nullslast())
    items = query.limit(limit).all()
    return jsonify(envelope(opportunity_schema.dump(items, many=True)))


@bp.get("/opportunities/tender-calendar")
@require_permission("bdc:read")
def tender_calendar():
    """BDC-04: upcoming submission deadlines across all tracked opportunities."""
    items = (
        Opportunity.query.filter(
            Opportunity.tenant_id == g.tenant_id,
            Opportunity.submission_deadline.isnot(None),
            Opportunity.stage.notin_(("won", "lost")),
        )
        .order_by(Opportunity.submission_deadline.asc())
        .all()
    )
    return jsonify(envelope(opportunity_schema.dump(items, many=True)))


@bp.post("/opportunities/<uuid:opportunity_id>/transition")
@require_permission("bdc:write")
def transition_opportunity(opportunity_id):
    opportunity = Opportunity.query.filter_by(id=opportunity_id, tenant_id=g.tenant_id).first()
    if not opportunity:
        raise APIError("Opportunity not found", status=404)

    try:
        data = StageTransitionSchema().load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))

    opportunity = services.transition_stage(opportunity, data["new_stage"], actor_id=g.user_id)
    return jsonify(opportunity_schema.dump(opportunity))


# --- Bid/No-Bid workflow (BDC-05) -----------------------------------------

@bp.post("/opportunities/<uuid:opportunity_id>/bid-no-bid")
@require_permission("bdc:write")
def bid_no_bid_decision(opportunity_id):
    opportunity = Opportunity.query.filter_by(id=opportunity_id, tenant_id=g.tenant_id).first()
    if not opportunity:
        raise APIError("Opportunity not found", status=404)

    try:
        data = BidNoBidDecisionSchema().load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))

    opportunity = services.record_bid_no_bid_decision(
        opportunity,
        decision=data["decision"],
        scorecard=data["scorecard"],
        rationale=data["rationale"],
        approver_id=g.user_id,
        reason_code=data.get("reason_code"),
    )
    return jsonify(opportunity_schema.dump(opportunity))


# --- Win/Loss (BDC-10, BDC-11) ---------------------------------------------

@bp.post("/opportunities/<uuid:opportunity_id>/win-loss")
@require_permission("bdc:write")
def record_win_loss(opportunity_id):
    opportunity = Opportunity.query.filter_by(id=opportunity_id, tenant_id=g.tenant_id).first()
    if not opportunity:
        raise APIError("Opportunity not found", status=404)

    try:
        data = WinLossRecordSchema().load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))
    data.pop("opportunity_id", None)

    record = services.record_win_loss(opportunity, **data)
    return jsonify(WinLossRecordSchema().dump(record)), 201


@bp.get("/opportunities/win-loss-summary")
@require_permission("bdc:read")
def win_loss_summary():
    """BDC-11: aggregate win/loss conversion report, grouped by client
    or value_band (see services.py for why "sector" isn't supported)."""
    group_by = request.args.get("group_by", "client")
    data = services.win_loss_summary(g.tenant_id, group_by=group_by)
    return jsonify(envelope(data))


# --- Competitors, Consultants, Government Agencies (BDC-06/07/08) ---------

@bp.get("/competitors")
@require_permission("bdc:read")
def list_competitors():
    items = Competitor.query.filter_by(tenant_id=g.tenant_id).order_by(Competitor.name).all()
    return jsonify(envelope(CompetitorSchema().dump(items, many=True)))


@bp.get("/consultants")
@require_permission("bdc:read")
def list_consultants():
    items = Consultant.query.filter_by(tenant_id=g.tenant_id).order_by(Consultant.name).all()
    return jsonify(envelope(ConsultantSchema().dump(items, many=True)))


@bp.get("/government-agencies")
@require_permission("bdc:read")
def list_government_agencies():
    items = GovernmentAgency.query.filter_by(tenant_id=g.tenant_id).order_by(GovernmentAgency.name).all()
    return jsonify(envelope(GovernmentAgencySchema().dump(items, many=True)))
