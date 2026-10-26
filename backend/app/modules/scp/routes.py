"""
Module 27 — Subcontractor Portal (Code: SCP)
Flask Blueprint. Base path: /v1/scp

Note on portal_user_id: every data-scoped route takes portal_user_id as
a URL parameter. The @require_permission grants on these routes are the
ORDINARY permission check (same mechanism as every other module); the
actual subcontractor-ownership scoping is NOT that permission check --
it's services.assert_subcontractor_owns_agreement/_certificate, called
unconditionally inside every service function regardless of what the
caller's permission grant says.

Real gap closed here, matching the identical fix made for Module 22
(CLP): nothing previously confirmed that the portal_user_id in the URL
was the SAME portal_user_id as the caller's own identity. A staff
admin token (scp:approve, no `is_portal_user` claim) legitimately
passes any portal_user_id -- that's the whole point of staff
administering subcontractor records. But a real subcontractor token
(scp:read/scp:write, `is_portal_user: true`) doing the same would let
one subcontractor act as any other, as long as they could guess or
observe another portal_user_id. `_get_portal_user_or_404` -- called
first by every route below -- closes that for every route in one
place: a portal token whose own id doesn't match the URL gets a 403
before anything else runs.
"""
from flask import Blueprint, g, jsonify, request
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity, get_jwt
from marshmallow import ValidationError

from app.extensions import db, limiter
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.auth import portal_reset  # noqa: F401  (registers PortalPasswordResetToken with the metadata)
from app.utils.pagination import envelope

from app.modules.scp import services
from app.modules.scp.models import SubcontractorPortalUser
from app.modules.scp.schemas import (
    SubcontractorPortalUserInputSchema,
    SubcontractorPortalUserSchema,
    SubmitProgressSchema,
    ProgressEntrySchema,
    PaymentCertificateSchema,
    SubmitClaimSchema,
    ClaimSchema,
    SubcontractorLoginSchema,
    ChangeSubcontractorPasswordSchema,
)

bp = Blueprint("scp", __name__, url_prefix="/v1/scp")

user_schema = SubcontractorPortalUserSchema()
progress_schema = ProgressEntrySchema()
certificate_schema = PaymentCertificateSchema()
claim_schema = ClaimSchema()

PORTAL_PERMISSIONS = ["scp:read", "scp:write"]


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_portal_user_or_404(portal_user_id) -> SubcontractorPortalUser:
    u = SubcontractorPortalUser.query.filter_by(id=portal_user_id, tenant_id=g.tenant_id).first()
    if not u:
        raise APIError("Subcontractor portal user not found", status=404)
    # See module docstring: a portal token may only ever act as itself.
    if g.get("is_portal_user") and str(portal_user_id) != str(g.user_id):
        raise APIError("You can only access your own account", status=403)
    return u


def _issue_portal_tokens(portal_user: SubcontractorPortalUser):
    claims = {
        "tenant_id": str(portal_user.tenant_id),
        "user_id": str(portal_user.id),
        "permissions": PORTAL_PERMISSIONS,
        "is_portal_user": True,
        "portal_kind": "scp",
        "pwd_ts": portal_user.password_changed_at.isoformat() if portal_user.password_changed_at else None,
    }
    access_token = create_access_token(identity=str(portal_user.id), additional_claims=claims)
    refresh_token = create_refresh_token(identity=str(portal_user.id), additional_claims=claims)
    return {"access_token": access_token, "refresh_token": refresh_token}


@bp.get("/health")
def health():
    return jsonify({"module": "scp", "name": "Subcontractor Portal", "status": "ok"})


# --- Subcontractor-facing authentication (portal build) ---------------------------
# Deliberately a SEPARATE endpoint family from /v1/auth/*, not an
# extension of it -- same reasoning as CLP's own auth family: a
# subcontractor session and a staff session should never be
# interchangeable. Self-service forgot/reset password lives in
# app/auth/portal_reset.py.

@bp.post("/auth/login")
@limiter.limit("10 per minute")
def portal_login():
    data = _load(SubcontractorLoginSchema())
    portal_user = services.authenticate_subcontractor_user(data["email"], data["password"])
    if not portal_user:
        return jsonify({"type": "about:blank", "title": "Invalid credentials", "status": 401}), 401
    return jsonify(_issue_portal_tokens(portal_user))


@bp.post("/auth/forgot-password")
@limiter.limit("5 per hour")
def portal_forgot_password():
    """Always the same 200 -- never reveals whether the email has an
    account (see app/auth/portal_reset.py)."""
    from app.auth.portal_reset import request_portal_password_reset
    from app.auth.schemas import ForgotPasswordSchema

    data = _load(ForgotPasswordSchema())
    request_portal_password_reset("scp", data["email"])
    return jsonify({"message": "If an account exists for that email, a reset link has been sent."})


@bp.post("/auth/reset-password")
@limiter.limit("10 per hour")
def portal_reset_password():
    from app.auth.portal_reset import reset_portal_password
    from app.auth.schemas import ResetPasswordSchema

    data = _load(ResetPasswordSchema())
    reset_portal_password("scp", data["token"], data["new_password"])
    return jsonify({"message": "Password reset successfully."})


@bp.post("/auth/refresh")
@jwt_required(refresh=True)
def portal_refresh():
    old_claims = get_jwt()
    if not old_claims.get("is_portal_user"):
        return jsonify({"type": "about:blank", "title": "Not a subcontractor session", "status": 401}), 401

    # A reset (or any password_changed_at change) kills older sessions:
    # this route is exempt from the tenant-context middleware's check.
    from app.auth.portal_reset import check_portal_pwd_ts

    if not check_portal_pwd_ts("scp", old_claims.get("tenant_id"), old_claims.get("user_id"), old_claims.get("pwd_ts")):
        return jsonify({"type": "about:blank", "title": "Session no longer valid", "status": 401}), 401

    identity = get_jwt_identity()
    new_claims = {
        "tenant_id": old_claims.get("tenant_id"),
        "user_id": old_claims.get("user_id"),
        "permissions": PORTAL_PERMISSIONS,
        "is_portal_user": True,
        "portal_kind": "scp",
        "pwd_ts": old_claims.get("pwd_ts"),
    }
    access_token = create_access_token(identity=identity, additional_claims=new_claims)

    from app.auth.jwt_utils import revoke_refresh_token
    import time

    old_jti = old_claims.get("jti")
    exp = old_claims.get("exp")
    if old_jti and exp:
        revoke_refresh_token(old_jti, expires_in_seconds=max(int(exp - time.time()), 1))
    refresh_token = create_refresh_token(identity=identity, additional_claims=new_claims)

    return jsonify({"access_token": access_token, "refresh_token": refresh_token})


@bp.post("/auth/logout")
@jwt_required(refresh=True)
def portal_logout():
    claims = get_jwt()
    from app.auth.jwt_utils import revoke_refresh_token
    import time

    jti = claims.get("jti")
    exp = claims.get("exp")
    if jti and exp:
        revoke_refresh_token(jti, expires_in_seconds=max(int(exp - time.time()), 1))
    return jsonify({"status": "logged out"})


@bp.get("/auth/me")
@require_permission("scp:read")
def portal_me():
    if not g.get("is_portal_user"):
        raise APIError("Not a subcontractor session", status=403)
    portal_user = _get_portal_user_or_404(g.user_id)
    return jsonify(user_schema.dump(portal_user))


@bp.post("/auth/me/password")
@require_permission("scp:write")
def portal_change_password():
    if not g.get("is_portal_user"):
        raise APIError("Not a subcontractor session", status=403)
    portal_user = _get_portal_user_or_404(g.user_id)
    data = _load(ChangeSubcontractorPasswordSchema())
    services.change_subcontractor_password(portal_user, **data)
    return jsonify({"status": "password updated"})


# --- Portal users --------------------------------------------------------------

@bp.post("/portal-users")
@require_permission("scp:approve")
def create_portal_user():
    data = _load(SubcontractorPortalUserInputSchema())
    password = data.pop("password")
    user = SubcontractorPortalUser(tenant_id=g.tenant_id, **data)
    db.session.add(user)
    db.session.flush()
    services.set_subcontractor_password(user, password=password)

    from app.modules.scp.models import SubcontractorPortalEmailIndex

    db.session.add(SubcontractorPortalEmailIndex(email=user.email, portal_user_id=user.id, tenant_id=g.tenant_id))
    db.session.commit()
    return jsonify(user_schema.dump(user)), 201


# --- Agreements (real, small addition -- see services.py's own docstring) --------

@bp.get("/portal-users/<uuid:portal_user_id>/agreements")
@require_permission("scp:read")
def list_agreements(portal_user_id):
    portal_user = _get_portal_user_or_404(portal_user_id)
    from app.modules.sub.schemas import SubcontractAgreementSchema

    agreements = services.list_agreements_for_subcontractor(g.tenant_id, portal_user=portal_user)
    return jsonify(envelope(SubcontractAgreementSchema().dump(agreements, many=True)))


@bp.get("/portal-users/<uuid:portal_user_id>/agreements/<uuid:agreement_id>")
@require_permission("scp:read")
def get_agreement(portal_user_id, agreement_id):
    portal_user = _get_portal_user_or_404(portal_user_id)
    from app.modules.sub.schemas import SubcontractAgreementSchema

    agreement = services.assert_subcontractor_owns_agreement(g.tenant_id, portal_user=portal_user, agreement_id=agreement_id)
    return jsonify(SubcontractAgreementSchema().dump(agreement))


# --- Progress submission (SUB-03, portal-facing half) ---------------------------

@bp.post("/portal-users/<uuid:portal_user_id>/progress-entries")
@require_permission("scp:write")
def submit_progress(portal_user_id):
    portal_user = _get_portal_user_or_404(portal_user_id)
    data = _load(SubmitProgressSchema())
    entry = services.submit_progress_as_subcontractor(g.tenant_id, portal_user=portal_user, **data)
    return jsonify(progress_schema.dump(entry)), 201


@bp.get("/portal-users/<uuid:portal_user_id>/progress-entries")
@require_permission("scp:read")
def list_progress_entries(portal_user_id):
    portal_user = _get_portal_user_or_404(portal_user_id)
    agreement_id = request.args.get("agreement_id")
    if not agreement_id:
        raise APIError("agreement_id query parameter is required", status=400)
    entries = services.get_progress_entries_for_subcontractor(g.tenant_id, portal_user=portal_user, agreement_id=agreement_id)
    return jsonify(envelope(progress_schema.dump(entries, many=True)))


# --- Payment certificate visibility (SUB-05/06, read-only) ----------------------

@bp.get("/portal-users/<uuid:portal_user_id>/payment-certificates")
@require_permission("scp:read")
def list_payment_certificates(portal_user_id):
    portal_user = _get_portal_user_or_404(portal_user_id)
    agreement_id = request.args.get("agreement_id")
    if not agreement_id:
        raise APIError("agreement_id query parameter is required", status=400)
    certs = services.get_payment_certificates_for_subcontractor(g.tenant_id, portal_user=portal_user, agreement_id=agreement_id)
    return jsonify(envelope(certificate_schema.dump(certs, many=True)))


# --- Claim submission (SUB-07) ---------------------------------------------------

@bp.post("/portal-users/<uuid:portal_user_id>/claims")
@require_permission("scp:write")
def submit_claim(portal_user_id):
    portal_user = _get_portal_user_or_404(portal_user_id)
    data = _load(SubmitClaimSchema())
    claim = services.submit_claim_as_subcontractor(g.tenant_id, portal_user=portal_user, **data)
    return jsonify(claim_schema.dump(claim)), 201


@bp.get("/portal-users/<uuid:portal_user_id>/claims")
@require_permission("scp:read")
def list_claims(portal_user_id):
    portal_user = _get_portal_user_or_404(portal_user_id)
    agreement_id = request.args.get("agreement_id")
    if not agreement_id:
        raise APIError("agreement_id query parameter is required", status=400)
    claims = services.get_claims_for_subcontractor(g.tenant_id, portal_user=portal_user, agreement_id=agreement_id)
    return jsonify(envelope(claim_schema.dump(claims, many=True)))


# --- Documents (portal) ---------------------------------------------------------------

@bp.post("/portal-users/<uuid:portal_user_id>/documents/upload-request")
@require_permission("scp:write")
def request_document_upload(portal_user_id):
    user = _get_portal_user_or_404(portal_user_id)
    from app.documents import portal as doc_portal
    from app.documents.schemas import PortalUploadRequestSchema, UploadRequestResponseSchema

    data = _load(PortalUploadRequestSchema())
    document, upload_url = doc_portal.create_upload(
        g.tenant_id, owner_type="scp", owner_id=user.subcontractor_id, user_id=user.id, **data
    )
    body = UploadRequestResponseSchema().dump(document)
    body["upload_url"] = upload_url
    return jsonify(body), 201


@bp.post("/portal-users/<uuid:portal_user_id>/documents/<uuid:document_id>/confirm")
@require_permission("scp:write")
def confirm_document_upload(portal_user_id, document_id):
    user = _get_portal_user_or_404(portal_user_id)
    from app.documents import portal as doc_portal
    from app.documents.schemas import DocumentSchema

    doc = doc_portal.confirm(
        g.tenant_id, owner_type="scp", owner_id=user.subcontractor_id, user_id=user.id, document_id=document_id
    )
    return jsonify(DocumentSchema().dump(doc))


@bp.get("/portal-users/<uuid:portal_user_id>/documents")
@require_permission("scp:read")
def list_documents(portal_user_id):
    user = _get_portal_user_or_404(portal_user_id)
    from app.documents import portal as doc_portal
    from app.documents.schemas import DocumentSchema

    docs = doc_portal.list_owned(g.tenant_id, owner_type="scp", owner_id=user.subcontractor_id)
    return jsonify(envelope(DocumentSchema().dump(docs, many=True)))


@bp.get("/portal-users/<uuid:portal_user_id>/documents/<uuid:document_id>/download")
@require_permission("scp:read")
def download_document(portal_user_id, document_id):
    user = _get_portal_user_or_404(portal_user_id)
    from app.documents import portal as doc_portal

    url = doc_portal.download_url(g.tenant_id, owner_type="scp", owner_id=user.subcontractor_id, document_id=document_id)
    return jsonify({"download_url": url})


@bp.delete("/portal-users/<uuid:portal_user_id>/documents/<uuid:document_id>")
@require_permission("scp:write")
def delete_document(portal_user_id, document_id):
    user = _get_portal_user_or_404(portal_user_id)
    from app.documents import portal as doc_portal

    doc_portal.delete_owned(g.tenant_id, owner_type="scp", owner_id=user.subcontractor_id, document_id=document_id)
    return "", 204
