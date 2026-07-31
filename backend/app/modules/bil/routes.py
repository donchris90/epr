"""
Module 18 — Client Billing (Code: BIL)
SRS Section 4.18 — Flask Blueprint. Base path: /v1/bil
"""
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.extensions import db
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import envelope

from app.modules.bil import services
from app.modules.bil.models import ProgressCertificate, VariationOrder, Claim, PaymentTracking
from app.modules.bil.schemas import (
    ProgressCertificateInputSchema,
    ProgressCertificateSchema,
    AddCertificateLineSchema,
    CertificateLineSchema,
    ApplyRetentionSchema,
    ApproveCertificateSchema,
    VariationOrderInputSchema,
    VariationOrderDecisionSchema,
    VariationOrderSchema,
    ClaimInputSchema,
    ClaimSchema,
    RecordPaymentSchema,
    PaymentTrackingSchema,
    RecognizeRevenueSchema,
    RevenueRecognitionSchema,
)

bp = Blueprint("bil", __name__, url_prefix="/v1/bil")

certificate_schema = ProgressCertificateSchema()
line_schema = CertificateLineSchema()
vo_schema = VariationOrderSchema()
claim_schema = ClaimSchema()
tracking_schema = PaymentTrackingSchema()
revenue_schema = RevenueRecognitionSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_certificate_or_404(certificate_id) -> ProgressCertificate:
    c = ProgressCertificate.query.filter_by(id=certificate_id, tenant_id=g.tenant_id).first()
    if not c:
        raise APIError("Progress certificate not found", status=404)
    return c


def _get_vo_or_404(vo_id) -> VariationOrder:
    vo = VariationOrder.query.filter_by(id=vo_id, tenant_id=g.tenant_id).first()
    if not vo:
        raise APIError("Variation order not found", status=404)
    return vo


@bp.get("/health")
def health():
    return jsonify({"module": "bil", "name": "Client Billing", "status": "ok"})


# --- Progress certificates (BIL-01, BIL-09) -------------------------------------

@bp.post("/certificates")
@require_permission("bil:write")
def create_certificate():
    data = _load(ProgressCertificateInputSchema())
    cert = ProgressCertificate(tenant_id=g.tenant_id, **data)
    db.session.add(cert)
    db.session.commit()
    return jsonify(certificate_schema.dump(cert)), 201


@bp.get("/certificates")
@require_permission("bil:read")
def list_certificates():
    status = request.args.get("status")
    query = ProgressCertificate.query.filter_by(tenant_id=g.tenant_id)
    if status:
        query = query.filter_by(status=status)
    certs = query.all()
    return jsonify(envelope(certificate_schema.dump(certs, many=True)))


@bp.get("/certificates/<uuid:certificate_id>")
@require_permission("bil:read")
def get_certificate(certificate_id):
    certificate = _get_certificate_or_404(certificate_id)
    body = certificate_schema.dump(certificate)
    body["lines"] = line_schema.dump(certificate.lines, many=True)
    body["payment_tracking"] = tracking_schema.dump(certificate.payment_tracking) if certificate.payment_tracking else None
    return jsonify(body)


@bp.post("/certificates/<uuid:certificate_id>/lines")
@require_permission("bil:write")
def add_certificate_line(certificate_id):
    certificate = _get_certificate_or_404(certificate_id)
    data = _load(AddCertificateLineSchema())
    line = services.add_certificate_line(g.tenant_id, certificate=certificate, **data)
    return jsonify(line_schema.dump(line)), 201


@bp.post("/certificates/<uuid:certificate_id>/apply-retention")
@require_permission("bil:write")
def apply_retention(certificate_id):
    certificate = _get_certificate_or_404(certificate_id)
    data = _load(ApplyRetentionSchema())
    certificate = services.apply_retention(certificate, **data)
    return jsonify(certificate_schema.dump(certificate))


@bp.post("/certificates/<uuid:certificate_id>/submit")
@require_permission("bil:write")
def submit_certificate(certificate_id):
    certificate = _get_certificate_or_404(certificate_id)
    certificate = services.submit_certificate(certificate)
    return jsonify(certificate_schema.dump(certificate))


@bp.post("/certificates/<uuid:certificate_id>/approve")
@require_permission("bil:approve")
def approve_certificate(certificate_id):
    certificate = _get_certificate_or_404(certificate_id)
    data = _load(ApproveCertificateSchema())
    certificate = services.approve_certificate(certificate, **data)
    return jsonify(certificate_schema.dump(certificate))


# --- Variation orders (BIL-04, business rule) -----------------------------------

@bp.post("/variation-orders")
@require_permission("bil:write")
def create_variation_order():
    data = _load(VariationOrderInputSchema())
    vo = VariationOrder(tenant_id=g.tenant_id, submitted_at=datetime.now(timezone.utc), **data)
    db.session.add(vo)
    db.session.commit()
    return jsonify(vo_schema.dump(vo)), 201


@bp.post("/variation-orders/<uuid:vo_id>/decide")
@require_permission("bil:approve")
def decide_variation_order(vo_id):
    vo = _get_vo_or_404(vo_id)
    if vo.status != "pending":
        raise APIError("Variation order has already been decided", status=409)

    data = _load(VariationOrderDecisionSchema())
    vo.status = data["decision"]
    vo.approved_by = data.get("approved_by")
    vo.approved_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(vo_schema.dump(vo))


@bp.get("/variation-orders")
@require_permission("bil:read")
def list_variation_orders():
    status = request.args.get("status")
    query = VariationOrder.query.filter_by(tenant_id=g.tenant_id)
    if status:
        query = query.filter_by(status=status)
    vos = query.all()
    return jsonify(envelope(vo_schema.dump(vos, many=True)))


# --- Claims (BIL-05) --------------------------------------------------------------

@bp.post("/claims")
@require_permission("bil:write")
def create_claim():
    data = _load(ClaimInputSchema())
    claim = Claim(tenant_id=g.tenant_id, submitted_at=datetime.now(timezone.utc), **data)
    db.session.add(claim)
    db.session.commit()
    return jsonify(claim_schema.dump(claim)), 201


# --- Payment tracking & aging (BIL-06, BIL-07) -----------------------------------

@bp.post("/payment-tracking/<uuid:tracking_id>/record-payment")
@require_permission("bil:write")
def record_payment(tracking_id):
    tracking = PaymentTracking.query.filter_by(id=tracking_id, tenant_id=g.tenant_id).first()
    if not tracking:
        raise APIError("Payment tracking record not found", status=404)
    data = _load(RecordPaymentSchema())
    tracking = services.record_payment(tracking, **data)
    return jsonify(tracking_schema.dump(tracking))


@bp.post("/payment-tracking/refresh-overdue")
@require_permission("bil:write")
def refresh_overdue():
    overdue = services.refresh_overdue_status(g.tenant_id)
    return jsonify(envelope(tracking_schema.dump(overdue, many=True)))


@bp.get("/outstanding-invoices")
@require_permission("bil:read")
def get_outstanding_invoices():
    report = services.get_outstanding_invoices_report(g.tenant_id)
    return jsonify(report)


# --- Revenue recognition (BIL-08, business rule) ---------------------------------

@bp.post("/revenue-recognition")
@require_permission("bil:approve")
def recognize_revenue():
    data = _load(RecognizeRevenueSchema())
    record = services.recognize_revenue(g.tenant_id, **data)
    return jsonify(revenue_schema.dump(record)), 201
