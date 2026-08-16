"""
Module 22 — Client Portal (Code: CLP)
SRS Section 4.22 — Flask Blueprint. Base path: /v1/clp

Note on client_user_id: every data-scoped route takes client_user_id as
a URL parameter. The @require_permission grants on these routes are the
ORDINARY permission check (same mechanism as every other module); the
actual client-to-project scoping is NOT that permission check -- it's
services.assert_client_project_access, called unconditionally inside
every service function regardless of what the caller's permission grant
says. See the module docstring in services.py for why that split matters.
"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.extensions import db
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import envelope

from app.modules.clp import services
from app.modules.clp.models import ClientPortalUser, ClientProjectAssignment, ClientRequest
from app.modules.clp.schemas import (
    ClientPortalUserInputSchema,
    ClientPortalUserSchema,
    ClientProjectAssignmentInputSchema,
    ClientProjectAssignmentSchema,
    ApprovalDecisionSchema,
    ClientApprovalActionSchema,
    ClientRequestInputSchema,
    ResolveClientRequestSchema,
    ClientRequestSchema,
)

bp = Blueprint("clp", __name__, url_prefix="/v1/clp")

user_schema = ClientPortalUserSchema()
assignment_schema = ClientProjectAssignmentSchema()
action_schema = ClientApprovalActionSchema()
request_schema = ClientRequestSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_client_user_or_404(client_user_id) -> ClientPortalUser:
    u = ClientPortalUser.query.filter_by(id=client_user_id, tenant_id=g.tenant_id).first()
    if not u:
        raise APIError("Client portal user not found", status=404)
    return u


def _get_client_request_or_404(request_id) -> ClientRequest:
    r = ClientRequest.query.filter_by(id=request_id, tenant_id=g.tenant_id).first()
    if not r:
        raise APIError("Client request not found", status=404)
    return r


@bp.get("/health")
def health():
    return jsonify({"module": "clp", "name": "Client Portal", "status": "ok"})


# --- Portal users & project assignment (CLP-08) -----------------------------------

@bp.post("/client-users")
@require_permission("clp:approve")
def create_client_user():
    data = _load(ClientPortalUserInputSchema())
    user = ClientPortalUser(tenant_id=g.tenant_id, **data)
    db.session.add(user)
    db.session.commit()
    return jsonify(user_schema.dump(user)), 201


@bp.post("/client-users/<uuid:client_user_id>/assignments")
@require_permission("clp:approve")
def assign_project(client_user_id):
    _get_client_user_or_404(client_user_id)
    data = _load(ClientProjectAssignmentInputSchema())
    assignment = ClientProjectAssignment(tenant_id=g.tenant_id, client_user_id=client_user_id, **data)
    db.session.add(assignment)
    db.session.commit()
    return jsonify(assignment_schema.dump(assignment)), 201


# --- Schedule review (CLP-01, CLP-06, business rule) --------------------------------

@bp.get("/client-users/<uuid:client_user_id>/projects/<uuid:project_id>/schedule")
@require_permission("clp:read")
def get_schedule(client_user_id, project_id):
    _get_client_user_or_404(client_user_id)
    activities = services.get_client_schedule_view(g.tenant_id, client_user_id=client_user_id, project_id=project_id)
    return jsonify(envelope(activities))


# --- Site media & diary summaries (CLP-02) --------------------------------------------

@bp.get("/client-users/<uuid:client_user_id>/projects/<uuid:project_id>/site-media")
@require_permission("clp:read")
def get_site_media(client_user_id, project_id):
    _get_client_user_or_404(client_user_id)
    result = services.get_client_site_media(g.tenant_id, client_user_id=client_user_id, project_id=project_id)
    return jsonify(result)


# --- Variation order & certificate approval (CLP-03, CLP-05) ---------------------------

@bp.post("/client-users/<uuid:client_user_id>/variation-orders/<uuid:vo_id>/decide")
@require_permission("clp:write")
def decide_variation_order(client_user_id, vo_id):
    _get_client_user_or_404(client_user_id)
    data = _load(ApprovalDecisionSchema())
    action = services.approve_variation_order_as_client(
        g.tenant_id, client_user_id=client_user_id, variation_order_id=vo_id, **data
    )
    return jsonify(action_schema.dump(action)), 201


@bp.post("/client-users/<uuid:client_user_id>/certificates/<uuid:certificate_id>/decide")
@require_permission("clp:write")
def decide_certificate(client_user_id, certificate_id):
    _get_client_user_or_404(client_user_id)
    data = _load(ApprovalDecisionSchema())
    action = services.approve_certificate_as_client(
        g.tenant_id, client_user_id=client_user_id, certificate_id=certificate_id, **data
    )
    return jsonify(action_schema.dump(action)), 201


# --- Client requests / RFIs (CLP-07) ------------------------------------------------------

@bp.post("/client-users/<uuid:client_user_id>/requests")
@require_permission("clp:write")
def submit_request(client_user_id):
    _get_client_user_or_404(client_user_id)
    data = _load(ClientRequestInputSchema())
    req = services.submit_client_request(g.tenant_id, client_user_id=client_user_id, **data)
    return jsonify(request_schema.dump(req)), 201


@bp.post("/requests/<uuid:request_id>/resolve")
@require_permission("clp:approve")
def resolve_request(request_id):
    req = _get_client_request_or_404(request_id)
    data = _load(ResolveClientRequestSchema())
    req = services.resolve_client_request(req, **data)
    return jsonify(request_schema.dump(req))


@bp.get("/client-users/<uuid:client_user_id>/requests")
@require_permission("clp:read")
def list_requests(client_user_id):
    _get_client_user_or_404(client_user_id)
    requests = ClientRequest.query.filter_by(tenant_id=g.tenant_id, client_user_id=client_user_id).all()
    return jsonify(envelope(request_schema.dump(requests, many=True)))
