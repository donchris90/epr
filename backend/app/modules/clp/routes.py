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

Real gap closed here, not present in the original CLP build: nothing
previously confirmed that the client_user_id in the URL was the SAME
client_user_id as the caller's own identity. A staff admin token
(clp:approve, no `is_client` claim) legitimately passes any
client_user_id -- that's the whole point of the admin page. But a real
client token (clp:read/clp:write, `is_client: true`) doing the same
would let one client act as any other, as long as they could guess or
observe another client_user_id. `_get_client_user_or_404` -- called
first by every route below -- now closes that for every route in one
place: a client token whose own id doesn't match the URL gets a 403
before anything else runs.
"""
from flask import Blueprint, g, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
)
from marshmallow import ValidationError

from app.extensions import db, limiter
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
    ClientLoginSchema,
    ClientProjectSummarySchema,
    ClientProjectDetailSchema,
    ClientDocumentSchema,
    ClientCertificateSchema,
    ClientVariationOrderSchema,
    ClientInvoiceSchema,
    ChangeClientPasswordSchema,
)

bp = Blueprint("clp", __name__, url_prefix="/v1/clp")

user_schema = ClientPortalUserSchema()
assignment_schema = ClientProjectAssignmentSchema()
action_schema = ClientApprovalActionSchema()
request_schema = ClientRequestSchema()
project_summary_schema = ClientProjectSummarySchema()
project_detail_schema = ClientProjectDetailSchema()
document_schema = ClientDocumentSchema()
certificate_schema = ClientCertificateSchema()
variation_order_schema = ClientVariationOrderSchema()
invoice_schema = ClientInvoiceSchema()

CLIENT_PERMISSIONS = ["clp:read", "clp:write"]


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_client_user_or_404(client_user_id) -> ClientPortalUser:
    u = ClientPortalUser.query.filter_by(id=client_user_id, tenant_id=g.tenant_id).first()
    if not u:
        raise APIError("Client portal user not found", status=404)
    # See module docstring: a client token may only ever act as itself.
    if g.get("is_client") and str(client_user_id) != str(g.user_id):
        raise APIError("You can only access your own account", status=403)
    return u


def _get_client_request_or_404(request_id) -> ClientRequest:
    r = ClientRequest.query.filter_by(id=request_id, tenant_id=g.tenant_id).first()
    if not r:
        raise APIError("Client request not found", status=404)
    return r


def _issue_client_tokens(client_user: ClientPortalUser):
    claims = {
        "tenant_id": str(client_user.tenant_id),
        "user_id": str(client_user.id),
        "permissions": CLIENT_PERMISSIONS,
        "is_client": True,
    }
    access_token = create_access_token(identity=str(client_user.id), additional_claims=claims)
    refresh_token = create_refresh_token(identity=str(client_user.id), additional_claims=claims)
    return {"access_token": access_token, "refresh_token": refresh_token}


@bp.get("/health")
def health():
    return jsonify({"module": "clp", "name": "Client Portal", "status": "ok"})


# --- Client-facing authentication (client portal build) --------------------------
# Deliberately a SEPARATE endpoint family from /v1/auth/*, not an
# extension of it: a client session and a staff session should never
# be interchangeable, and keeping them on different routes means a
# client token literally cannot reach an internal-only endpoint family
# by construction, not just by convention. See
# docs/CLIENT_PORTAL_GAPS.md for the full reasoning and what a
# self-service "forgot password" flow would still need.

@bp.post("/auth/login")
@limiter.limit("10 per minute")
def client_login():
    data = _load(ClientLoginSchema())
    client_user = services.authenticate_client_user(data["email"], data["password"])
    if not client_user:
        return jsonify({"type": "about:blank", "title": "Invalid credentials", "status": 401}), 401
    return jsonify(_issue_client_tokens(client_user))


@bp.post("/auth/refresh")
@jwt_required(refresh=True)
def client_refresh():
    old_claims = get_jwt()
    if not old_claims.get("is_client"):
        # A staff refresh token has no business minting a client-shaped
        # access token, or vice versa -- see the login-family docstring.
        return jsonify({"type": "about:blank", "title": "Not a client session", "status": 401}), 401

    identity = get_jwt_identity()
    new_claims = {
        "tenant_id": old_claims.get("tenant_id"),
        "user_id": old_claims.get("user_id"),
        "permissions": CLIENT_PERMISSIONS,
        "is_client": True,
    }
    access_token = create_access_token(identity=identity, additional_claims=new_claims)

    from app.auth.jwt_utils import revoke_refresh_token

    old_jti = old_claims.get("jti")
    exp = old_claims.get("exp")
    import time

    if old_jti and exp:
        revoke_refresh_token(old_jti, expires_in_seconds=max(int(exp - time.time()), 1))
    refresh_token = create_refresh_token(identity=identity, additional_claims=new_claims)

    return jsonify({"access_token": access_token, "refresh_token": refresh_token})


@bp.post("/auth/logout")
@jwt_required(refresh=True)
def client_logout():
    claims = get_jwt()
    from app.auth.jwt_utils import revoke_refresh_token
    import time

    jti = claims.get("jti")
    exp = claims.get("exp")
    if jti and exp:
        revoke_refresh_token(jti, expires_in_seconds=max(int(exp - time.time()), 1))
    return jsonify({"status": "logged out"})


@bp.get("/auth/me")
@require_permission("clp:read")
def client_me():
    if not g.get("is_client"):
        raise APIError("Not a client session", status=403)
    client_user = _get_client_user_or_404(g.user_id)
    return jsonify(user_schema.dump(client_user))


@bp.post("/auth/me/password")
@require_permission("clp:write")
def client_change_password():
    if not g.get("is_client"):
        raise APIError("Not a client session", status=403)
    client_user = _get_client_user_or_404(g.user_id)
    data = _load(ChangeClientPasswordSchema())
    services.change_client_password(client_user, **data)
    return jsonify({"status": "password updated"})


# --- Portal users & project assignment (CLP-08) -----------------------------------

@bp.post("/client-users")
@require_permission("clp:approve")
def create_client_user():
    data = _load(ClientPortalUserInputSchema())
    password = data.pop("password")
    user = ClientPortalUser(tenant_id=g.tenant_id, **data)
    db.session.add(user)
    db.session.flush()
    services.set_client_password(user, password=password)

    from app.modules.clp.models import ClientPortalEmailIndex

    db.session.add(ClientPortalEmailIndex(tenant_id=g.tenant_id, email=user.email, client_user_id=user.id))
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


@bp.get("/client-users/<uuid:client_user_id>/assignments")
@require_permission("clp:read")
def list_assignments(client_user_id):
    _get_client_user_or_404(client_user_id)
    assignments = ClientProjectAssignment.query.filter_by(tenant_id=g.tenant_id, client_user_id=client_user_id).all()
    return jsonify(envelope(assignment_schema.dump(assignments, many=True)))


# --- Dashboard / project list & detail (client portal build) ---------------------

@bp.get("/client-users/<uuid:client_user_id>/projects")
@require_permission("clp:read")
def list_projects(client_user_id):
    _get_client_user_or_404(client_user_id)
    projects = services.list_assigned_projects(g.tenant_id, client_user_id=client_user_id)
    return jsonify(envelope(project_summary_schema.dump(projects, many=True)))


@bp.get("/client-users/<uuid:client_user_id>/projects/<uuid:project_id>")
@require_permission("clp:read")
def get_project(client_user_id, project_id):
    _get_client_user_or_404(client_user_id)
    result = services.get_client_project_detail(g.tenant_id, client_user_id=client_user_id, project_id=project_id)
    body = project_detail_schema.dump(result["project"])
    body["contract_value"] = str(result["contract_value"]) if result["contract_value"] is not None else None
    body["currency"] = result["currency"]
    return jsonify(body)


@bp.get("/client-users/<uuid:client_user_id>/projects/<uuid:project_id>/progress")
@require_permission("clp:read")
def get_progress(client_user_id, project_id):
    _get_client_user_or_404(client_user_id)
    summary = services.get_client_progress_summary(g.tenant_id, client_user_id=client_user_id, project_id=project_id)
    return jsonify(summary)


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


# --- Documents & drawings (client portal build) -----------------------------------
# "Drawings" is the same Document row set, filtered to doc_type=drawing
# -- there is no separate drawing-register/versioning entity anywhere
# in this codebase. See docs/CLIENT_PORTAL_GAPS.md.

@bp.get("/client-users/<uuid:client_user_id>/projects/<uuid:project_id>/documents")
@require_permission("clp:read")
def get_documents(client_user_id, project_id):
    _get_client_user_or_404(client_user_id)
    doc_type = request.args.get("doc_type")
    documents = services.get_client_documents(g.tenant_id, client_user_id=client_user_id, project_id=project_id, doc_type=doc_type)
    return jsonify(envelope(document_schema.dump(documents, many=True)))


@bp.get("/client-users/<uuid:client_user_id>/projects/<uuid:project_id>/documents/<uuid:document_id>/download")
@require_permission("clp:read")
def download_document(client_user_id, project_id, document_id):
    _get_client_user_or_404(client_user_id)
    url = services.get_client_document_download_url(
        g.tenant_id, client_user_id=client_user_id, project_id=project_id, document_id=document_id
    )
    return jsonify({"download_url": url})


# --- Certificates & variations (client portal build) ------------------------------

@bp.get("/client-users/<uuid:client_user_id>/projects/<uuid:project_id>/certificates")
@require_permission("clp:read")
def get_certificates(client_user_id, project_id):
    _get_client_user_or_404(client_user_id)
    certificates = services.get_client_certificates(g.tenant_id, client_user_id=client_user_id, project_id=project_id)
    return jsonify(envelope(certificate_schema.dump(certificates, many=True)))


@bp.get("/client-users/<uuid:client_user_id>/projects/<uuid:project_id>/variation-orders")
@require_permission("clp:read")
def get_variation_orders(client_user_id, project_id):
    _get_client_user_or_404(client_user_id)
    variation_orders = services.get_client_variation_orders(g.tenant_id, client_user_id=client_user_id, project_id=project_id)
    return jsonify(envelope(variation_order_schema.dump(variation_orders, many=True)))


# --- Invoices & payments (client portal build) -------------------------------------
# There is no separate "invoice" entity anywhere in this codebase; a
# submitted ProgressCertificate IS the invoice, and PaymentTracking is
# its payment status. See services.get_client_invoices.

@bp.get("/client-users/<uuid:client_user_id>/projects/<uuid:project_id>/invoices")
@require_permission("clp:read")
def get_invoices(client_user_id, project_id):
    _get_client_user_or_404(client_user_id)
    invoices = services.get_client_invoices(g.tenant_id, client_user_id=client_user_id, project_id=project_id)
    return jsonify(envelope(invoice_schema.dump(invoices, many=True)))


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


@bp.get("/client-users/<uuid:client_user_id>/approval-actions")
@require_permission("clp:read")
def list_approval_actions(client_user_id):
    _get_client_user_or_404(client_user_id)
    from app.modules.clp.models import ClientApprovalAction

    actions = ClientApprovalAction.query.filter_by(tenant_id=g.tenant_id, client_user_id=client_user_id).order_by(
        ClientApprovalAction.decided_at.desc()
    ).all()
    return jsonify(envelope(action_schema.dump(actions, many=True)))


# --- Client requests / RFIs / issues / messages (CLP-07) --------------------------
# Doubles as "Issues" and "Messages" in the client portal: there is no
# dedicated issue-tracking or messaging entity a client can safely see
# (NCR/punch-list records in QMS are internal QA artifacts, not
# curated for client visibility, and have no clp proxy). A
# ClientRequest with request_type='rfi' is used for both; see
# docs/CLIENT_PORTAL_GAPS.md.

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
    project_id = request.args.get("project_id")
    query = ClientRequest.query.filter_by(tenant_id=g.tenant_id, client_user_id=client_user_id)
    if project_id:
        query = query.filter_by(project_id=project_id)
    requests = query.order_by(ClientRequest.submitted_at.desc()).all()
    return jsonify(envelope(request_schema.dump(requests, many=True)))

