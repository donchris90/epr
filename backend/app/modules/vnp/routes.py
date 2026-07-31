"""
Module 23 — Vendor Portal (Code: VNP)
SRS Section 4.23 — Flask Blueprint. Base path: /v1/vnp
"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.extensions import db
from app.utils.decorators import require_permission
from app.utils.errors import APIError
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
    UploadInvoiceSchema,
    InvoiceUploadSchema,
    SubmitBankingChangeSchema,
    RejectBankingChangeSchema,
    BankingChangeRequestSchema,
)

bp = Blueprint("vnp", __name__, url_prefix="/v1/vnp")

user_schema = VendorPortalUserSchema()
ack_schema = OrderAcknowledgmentSchema()
quote_schema = QuotationSchema()
upload_schema = InvoiceUploadSchema()
banking_schema = BankingChangeRequestSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_vendor_user_or_404(vendor_user_id) -> VendorPortalUser:
    u = VendorPortalUser.query.filter_by(id=vendor_user_id, tenant_id=g.tenant_id).first()
    if not u:
        raise APIError("Vendor portal user not found", status=404)
    return u


def _get_banking_request_or_404(request_id) -> VendorBankingChangeRequest:
    r = VendorBankingChangeRequest.query.filter_by(id=request_id, tenant_id=g.tenant_id).first()
    if not r:
        raise APIError("Banking change request not found", status=404)
    return r


@bp.get("/health")
def health():
    return jsonify({"module": "vnp", "name": "Vendor Portal", "status": "ok"})


# --- Portal users ------------------------------------------------------------------

@bp.post("/vendor-users")
@require_permission("vnp:approve")
def create_vendor_user():
    data = _load(VendorPortalUserInputSchema())
    user = VendorPortalUser(tenant_id=g.tenant_id, **data)
    db.session.add(user)
    db.session.commit()
    return jsonify(user_schema.dump(user)), 201


# --- Order acknowledgment (VNP-01) --------------------------------------------------

@bp.post("/vendor-users/<uuid:vendor_user_id>/acknowledge-order")
@require_permission("vnp:write")
def acknowledge_order(vendor_user_id):
    vendor_user = _get_vendor_user_or_404(vendor_user_id)
    data = _load(AcknowledgeOrderSchema())
    ack = services.acknowledge_order(g.tenant_id, vendor_user=vendor_user, **data)
    return jsonify(ack_schema.dump(ack)), 201


# --- Quote submission (VNP-02) -------------------------------------------------------

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
