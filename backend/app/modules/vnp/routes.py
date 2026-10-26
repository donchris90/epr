"""
Module 23 — Vendor Portal (Code: VNP)
SRS Section 4.23 — Flask Blueprint. Base path: /v1/vnp

Note on vendor_user_id: every data-scoped route takes vendor_user_id as
a URL parameter. The @require_permission grants on these routes are the
ORDINARY permission check (same mechanism as every other module); the
actual vendor-ownership scoping is NOT that permission check -- it's
services.assert_vendor_owns_purchase_order/_invited_to_rfq, called
unconditionally inside every service function regardless of what the
caller's permission grant says.

Real gap closed here, matching the identical fix made for Module 22
(CLP) and Module 27 (SCP): nothing previously confirmed that the
vendor_user_id in the URL was the SAME vendor_user_id as the caller's
own identity. `_get_vendor_user_or_404` -- called first by every route
below -- closes that: a vendor token whose own id doesn't match the
URL gets a 403 before anything else runs.
"""
from flask import Blueprint, g, jsonify, request
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity, get_jwt
from marshmallow import ValidationError

from app.extensions import db, limiter
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.auth import portal_reset  # noqa: F401  (registers PortalPasswordResetToken with the metadata)
from app.utils.pagination import envelope

from app.modules.vnp import services
from app.modules.vnp.models import VendorPortalUser, VendorBankingChangeRequest
from app.modules.vnp.schemas import (
    VendorPortalUserInputSchema,
    VendorPortalUserSchema,
    AcknowledgeOrderSchema,
    OrderAcknowledgmentSchema,
    SubmitQuoteSchema,
    QuotationSchema,
    RFQInvitationSchema,
    UploadInvoiceSchema,
    InvoiceUploadSchema,
    SubmitBankingChangeSchema,
    RejectBankingChangeSchema,
    BankingChangeRequestSchema,
    VendorLoginSchema,
    ChangeVendorPasswordSchema,
)

bp = Blueprint("vnp", __name__, url_prefix="/v1/vnp")

user_schema = VendorPortalUserSchema()
ack_schema = OrderAcknowledgmentSchema()
quote_schema = QuotationSchema()
upload_schema = InvoiceUploadSchema()
banking_schema = BankingChangeRequestSchema()

PORTAL_PERMISSIONS = ["vnp:read", "vnp:write"]


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_vendor_user_or_404(vendor_user_id) -> VendorPortalUser:
    u = VendorPortalUser.query.filter_by(id=vendor_user_id, tenant_id=g.tenant_id).first()
    if not u:
        raise APIError("Vendor portal user not found", status=404)
    # See module docstring: a vendor token may only ever act as itself.
    if g.get("is_portal_user") and str(vendor_user_id) != str(g.user_id):
        raise APIError("You can only access your own account", status=403)
    return u


def _get_banking_request_or_404(request_id) -> VendorBankingChangeRequest:
    r = VendorBankingChangeRequest.query.filter_by(id=request_id, tenant_id=g.tenant_id).first()
    if not r:
        raise APIError("Banking change request not found", status=404)
    return r


def _issue_portal_tokens(vendor_user: VendorPortalUser):
    claims = {
        "tenant_id": str(vendor_user.tenant_id),
        "user_id": str(vendor_user.id),
        "permissions": PORTAL_PERMISSIONS,
        "is_portal_user": True,
        "portal_kind": "vnp",
        "pwd_ts": vendor_user.password_changed_at.isoformat() if vendor_user.password_changed_at else None,
    }
    access_token = create_access_token(identity=str(vendor_user.id), additional_claims=claims)
    refresh_token = create_refresh_token(identity=str(vendor_user.id), additional_claims=claims)
    return {"access_token": access_token, "refresh_token": refresh_token}


@bp.get("/health")
def health():
    return jsonify({"module": "vnp", "name": "Vendor Portal", "status": "ok"})


# --- Vendor-facing authentication (portal build) -----------------------------------
# Deliberately a SEPARATE endpoint family from /v1/auth/*, not an
# extension of it -- same reasoning as CLP/SCP's own auth families.
# Self-service forgot/reset password: app/auth/portal_reset.py.

@bp.post("/auth/login")
@limiter.limit("10 per minute")
def portal_login():
    data = _load(VendorLoginSchema())
    vendor_user = services.authenticate_vendor_user(data["email"], data["password"])
    if not vendor_user:
        return jsonify({"type": "about:blank", "title": "Invalid credentials", "status": 401}), 401
    return jsonify(_issue_portal_tokens(vendor_user))


@bp.post("/auth/forgot-password")
@limiter.limit("5 per hour")
def portal_forgot_password():
    """Always the same 200 -- never reveals whether the email has an
    account (see app/auth/portal_reset.py)."""
    from app.auth.portal_reset import request_portal_password_reset
    from app.auth.schemas import ForgotPasswordSchema

    data = _load(ForgotPasswordSchema())
    request_portal_password_reset("vnp", data["email"])
    return jsonify({"message": "If an account exists for that email, a reset link has been sent."})


@bp.post("/auth/reset-password")
@limiter.limit("10 per hour")
def portal_reset_password():
    from app.auth.portal_reset import reset_portal_password
    from app.auth.schemas import ResetPasswordSchema

    data = _load(ResetPasswordSchema())
    reset_portal_password("vnp", data["token"], data["new_password"])
    return jsonify({"message": "Password reset successfully."})


@bp.post("/auth/refresh")
@jwt_required(refresh=True)
def portal_refresh():
    old_claims = get_jwt()
    if not old_claims.get("is_portal_user"):
        return jsonify({"type": "about:blank", "title": "Not a vendor session", "status": 401}), 401

    # A reset (or any password_changed_at change) kills older sessions:
    # this route is exempt from the tenant-context middleware's check.
    from app.auth.portal_reset import check_portal_pwd_ts

    if not check_portal_pwd_ts("vnp", old_claims.get("tenant_id"), old_claims.get("user_id"), old_claims.get("pwd_ts")):
        return jsonify({"type": "about:blank", "title": "Session no longer valid", "status": 401}), 401

    identity = get_jwt_identity()
    new_claims = {
        "tenant_id": old_claims.get("tenant_id"),
        "user_id": old_claims.get("user_id"),
        "permissions": PORTAL_PERMISSIONS,
        "is_portal_user": True,
        "portal_kind": "vnp",
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
@require_permission("vnp:read")
def portal_me():
    if not g.get("is_portal_user"):
        raise APIError("Not a vendor session", status=403)
    vendor_user = _get_vendor_user_or_404(g.user_id)
    return jsonify(user_schema.dump(vendor_user))


@bp.post("/auth/me/password")
@require_permission("vnp:write")
def portal_change_password():
    if not g.get("is_portal_user"):
        raise APIError("Not a vendor session", status=403)
    vendor_user = _get_vendor_user_or_404(g.user_id)
    data = _load(ChangeVendorPasswordSchema())
    services.change_vendor_password(vendor_user, **data)
    return jsonify({"status": "password updated"})


# --- Portal users ------------------------------------------------------------------

@bp.post("/vendor-users")
@require_permission("vnp:approve")
def create_vendor_user():
    data = _load(VendorPortalUserInputSchema())
    password = data.pop("password")
    user = VendorPortalUser(tenant_id=g.tenant_id, **data)
    db.session.add(user)
    db.session.flush()
    services.set_vendor_password(user, password=password)

    from app.modules.vnp.models import VendorPortalEmailIndex

    db.session.add(VendorPortalEmailIndex(email=user.email, vendor_user_id=user.id, tenant_id=g.tenant_id))
    db.session.commit()
    return jsonify(user_schema.dump(user)), 201


# --- Purchase orders (real, small addition -- see services.py's own docstring) -----

@bp.get("/vendor-users/<uuid:vendor_user_id>/purchase-orders")
@require_permission("vnp:read")
def list_purchase_orders(vendor_user_id):
    vendor_user = _get_vendor_user_or_404(vendor_user_id)
    from app.modules.prc.schemas import PurchaseOrderSchema

    orders = services.list_purchase_orders_for_vendor(g.tenant_id, vendor_user=vendor_user)
    return jsonify(envelope(PurchaseOrderSchema().dump(orders, many=True)))


# --- Order acknowledgment (VNP-01) --------------------------------------------------

@bp.post("/vendor-users/<uuid:vendor_user_id>/acknowledge-order")
@require_permission("vnp:write")
def acknowledge_order(vendor_user_id):
    vendor_user = _get_vendor_user_or_404(vendor_user_id)
    data = _load(AcknowledgeOrderSchema())
    ack = services.acknowledge_order(g.tenant_id, vendor_user=vendor_user, **data)
    return jsonify(ack_schema.dump(ack)), 201


# --- Quote submission (VNP-02) -------------------------------------------------------

@bp.get("/vendor-users/<uuid:vendor_user_id>/rfq-invitations")
@require_permission("vnp:read")
def list_rfq_invitations(vendor_user_id):
    vendor_user = _get_vendor_user_or_404(vendor_user_id)
    items = services.list_rfq_invitations_for_vendor(g.tenant_id, vendor_user=vendor_user)
    return jsonify(envelope(RFQInvitationSchema().dump(items, many=True)))


@bp.post("/vendor-users/<uuid:vendor_user_id>/quotes")
@require_permission("vnp:write")
def submit_quote(vendor_user_id):
    vendor_user = _get_vendor_user_or_404(vendor_user_id)
    data = _load(SubmitQuoteSchema())
    quotation = services.submit_quote_as_vendor(g.tenant_id, vendor_user=vendor_user, **data)
    return jsonify(quote_schema.dump(quotation)), 201


# --- Invoice upload & payment tracking (VNP-03, VNP-04) --------------------------------

@bp.post("/vendor-users/<uuid:vendor_user_id>/invoices")
@require_permission("vnp:write")
def upload_invoice(vendor_user_id):
    vendor_user = _get_vendor_user_or_404(vendor_user_id)
    data = _load(UploadInvoiceSchema())
    upload = services.upload_vendor_invoice(g.tenant_id, vendor_user=vendor_user, **data)
    return jsonify(upload_schema.dump(upload)), 201


@bp.get("/vendor-users/<uuid:vendor_user_id>/invoices")
@require_permission("vnp:read")
def list_invoices(vendor_user_id):
    vendor_user = _get_vendor_user_or_404(vendor_user_id)
    uploads = services.get_vendor_invoice_uploads(g.tenant_id, vendor_user=vendor_user)
    return jsonify(envelope(upload_schema.dump(uploads, many=True)))


# --- Banking detail change (VNP-05, business rule) --------------------------------------

@bp.post("/vendor-users/<uuid:vendor_user_id>/banking-change-requests")
@require_permission("vnp:write")
def submit_banking_change(vendor_user_id):
    """Reachable by an ordinary vendor-portal session -- notice this
    route requires only `vnp:write`, never the internal-only
    `vnp:finance_approve` grant the routes below require."""
    vendor_user = _get_vendor_user_or_404(vendor_user_id)
    data = _load(SubmitBankingChangeSchema())
    req = services.submit_banking_change(g.tenant_id, vendor_user=vendor_user, **data)
    return jsonify(banking_schema.dump(req)), 201


@bp.get("/vendor-users/<uuid:vendor_user_id>/banking-change-requests")
@require_permission("vnp:read")
def list_own_banking_change_requests(vendor_user_id):
    """The vendor's own requests (newest first), so the portal can show
    status and any rejection reason. Ownership-scoped like every other
    vendor-user route; the staff queue below is a separate, finance-only
    endpoint."""
    vendor_user = _get_vendor_user_or_404(vendor_user_id)
    reqs = (
        VendorBankingChangeRequest.query.filter_by(tenant_id=g.tenant_id, vendor_user_id=vendor_user.id)
        .order_by(VendorBankingChangeRequest.submitted_at.desc())
        .all()
    )
    return jsonify(envelope(banking_schema.dump(reqs, many=True)))


@bp.post("/banking-change-requests/<uuid:request_id>/approve")
@require_permission("vnp:finance_approve")
def approve_banking_change(request_id):
    """Business rule: gated behind `vnp:finance_approve` specifically
    -- a distinct, internal-only permission a vendor-portal session
    should never be granted, on top of the fact that this route isn't
    even reachable from the vendor-facing side of the application."""
    req = _get_banking_request_or_404(request_id)
    req = services.approve_banking_change(req, approved_by=g.user_id)
    return jsonify(banking_schema.dump(req))


@bp.post("/banking-change-requests/<uuid:request_id>/reject")
@require_permission("vnp:finance_approve")
def reject_banking_change(request_id):
    req = _get_banking_request_or_404(request_id)
    data = _load(RejectBankingChangeSchema())
    req = services.reject_banking_change(req, reviewed_by=g.user_id, **data)
    return jsonify(banking_schema.dump(req))


@bp.get("/banking-change-requests")
@require_permission("vnp:finance_approve")
def list_banking_change_requests():
    status = request.args.get("status", "pending")
    reqs = VendorBankingChangeRequest.query.filter_by(tenant_id=g.tenant_id, status=status).all()
    return jsonify(envelope(banking_schema.dump(reqs, many=True)))
