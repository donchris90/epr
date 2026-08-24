"""
Module 12 — Subcontractor Management (Code: SUB)
SRS Section 4.12 — Flask Blueprint. Base path: /v1/sub
"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.extensions import db
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import envelope

from app.modules.sub import services
from app.modules.sub.models import (
    Subcontractor,
    SubcontractAgreement,
    SubcontractScopeItem,
    SubcontractProgressEntry,
    MeasurementSheet,
    PaymentCertificate,
    BackCharge,
    SubcontractRetention,
    SubcontractClaim,
    PerformanceRating,
    ComplianceDocument,
)
from app.modules.sub.schemas import (
    SubcontractorSchema,
    SubcontractAgreementSchema,
    SubcontractScopeItemSchema,
    SubcontractProgressEntrySchema,
    MeasurementSheetInputSchema,
    MeasurementSheetSchema,
    IssuePaymentCertificateSchema,
    PaymentCertificateSchema,
    BackChargeInputSchema,
    BackChargeSchema,
    SubcontractRetentionSchema,
    ReleaseRetentionSchema,
    SubcontractClaimInputSchema,
    SubcontractClaimSchema,
    ClaimReviewSchema,
    PerformanceRatingInputSchema,
    PerformanceRatingSchema,
    ComplianceDocumentInputSchema,
    ComplianceDocumentSchema,
)

bp = Blueprint("sub", __name__, url_prefix="/v1/sub")

subcontractor_schema = SubcontractorSchema()
agreement_schema = SubcontractAgreementSchema()
scope_item_schema = SubcontractScopeItemSchema()
progress_schema = SubcontractProgressEntrySchema()
measurement_schema = MeasurementSheetSchema()
certificate_schema = PaymentCertificateSchema()
back_charge_schema = BackChargeSchema()
retention_schema = SubcontractRetentionSchema()
claim_schema = SubcontractClaimSchema()
rating_schema = PerformanceRatingSchema()
compliance_schema = ComplianceDocumentSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_subcontractor_or_404(subcontractor_id) -> Subcontractor:
    s = Subcontractor.query.filter_by(id=subcontractor_id, tenant_id=g.tenant_id).first()
    if not s:
        raise APIError("Subcontractor not found", status=404)
    return s


def _get_agreement_or_404(agreement_id) -> SubcontractAgreement:
    a = SubcontractAgreement.query.filter_by(id=agreement_id, tenant_id=g.tenant_id).first()
    if not a:
        raise APIError("Subcontract agreement not found", status=404)
    return a


@bp.get("/health")
def health():
    return jsonify({"module": "sub", "name": "Subcontractor Management", "status": "ok"})


# --- Subcontractors ------------------------------------------------------------

@bp.post("/subcontractors")
@require_permission("sub:write")
def create_subcontractor():
    data = _load(subcontractor_schema)
    sub = Subcontractor(tenant_id=g.tenant_id, **data)
    db.session.add(sub)
    db.session.commit()
    return jsonify(subcontractor_schema.dump(sub)), 201


@bp.get("/subcontractors")
@require_permission("sub:read")
def list_subcontractors():
    subs = Subcontractor.query.filter_by(tenant_id=g.tenant_id).all()
    return jsonify(envelope(subcontractor_schema.dump(subs, many=True)))


@bp.get("/subcontractors/<uuid:subcontractor_id>")
@require_permission("sub:read")
def get_subcontractor(subcontractor_id):
    return jsonify(subcontractor_schema.dump(_get_subcontractor_or_404(subcontractor_id)))


# --- Agreements & scope (SUB-01, SUB-02) ---------------------------------------

@bp.post("/agreements")
@require_permission("sub:write")
def create_agreement():
    data = _load(agreement_schema)
    _get_subcontractor_or_404(data["subcontractor_id"])
    agreement = SubcontractAgreement(tenant_id=g.tenant_id, **data)
    db.session.add(agreement)
    db.session.commit()
    return jsonify(agreement_schema.dump(agreement)), 201


@bp.get("/agreements")
@require_permission("sub:read")
def list_agreements():
    agreements = SubcontractAgreement.query.filter_by(tenant_id=g.tenant_id).all()
    return jsonify(envelope(agreement_schema.dump(agreements, many=True)))


@bp.get("/agreements/<uuid:agreement_id>")
@require_permission("sub:read")
def get_agreement(agreement_id):
    """Real, previously genuinely missing -- the staff-facing side of
    this module had no single-agreement detail endpoint at all (only
    the Subcontractor Portal's own, separately-scoped equivalent
    existed, built earlier this session for SCP -- see
    subcontractor-portal/hooks.ts -- which is a different, portal-
    authenticated endpoint, not this internal one)."""
    return jsonify(agreement_schema.dump(_get_agreement_or_404(agreement_id)))


@bp.post("/agreements/<uuid:agreement_id>/scope-items")
@require_permission("sub:write")
def add_scope_item(agreement_id):
    agreement = _get_agreement_or_404(agreement_id)
    data = _load(scope_item_schema)
    item = SubcontractScopeItem(tenant_id=g.tenant_id, agreement_id=agreement.id, **data)
    db.session.add(item)
    db.session.commit()
    return jsonify(scope_item_schema.dump(item)), 201


@bp.get("/agreements/<uuid:agreement_id>/scope-items")
@require_permission("sub:read")
def list_scope_items(agreement_id):
    _get_agreement_or_404(agreement_id)
    items = SubcontractScopeItem.query.filter_by(agreement_id=agreement_id, tenant_id=g.tenant_id).all()
    return jsonify(envelope(scope_item_schema.dump(items, many=True)))


# --- Progress & measurement (SUB-03, SUB-04) -----------------------------------

@bp.post("/agreements/<uuid:agreement_id>/progress-entries")
@require_permission("sub:write")
def submit_progress(agreement_id):
    agreement = _get_agreement_or_404(agreement_id)
    data = _load(progress_schema)
    entry = SubcontractProgressEntry(tenant_id=g.tenant_id, agreement_id=agreement.id, **data)
    db.session.add(entry)
    db.session.commit()
    return jsonify(progress_schema.dump(entry)), 201


@bp.get("/agreements/<uuid:agreement_id>/progress-entries")
@require_permission("sub:read")
def list_progress_entries(agreement_id):
    _get_agreement_or_404(agreement_id)
    entries = SubcontractProgressEntry.query.filter_by(agreement_id=agreement_id, tenant_id=g.tenant_id).all()
    return jsonify(envelope(progress_schema.dump(entries, many=True)))


@bp.post("/measurement-sheets")
@require_permission("sub:write")
def create_measurement_sheet():
    data = _load(MeasurementSheetInputSchema())
    _get_agreement_or_404(data["agreement_id"])
    sheet = MeasurementSheet(tenant_id=g.tenant_id, **data)
    db.session.add(sheet)
    db.session.commit()
    return jsonify(measurement_schema.dump(sheet)), 201


@bp.get("/agreements/<uuid:agreement_id>/measurement-sheets")
@require_permission("sub:read")
def list_measurement_sheets(agreement_id):
    _get_agreement_or_404(agreement_id)
    sheets = MeasurementSheet.query.filter_by(agreement_id=agreement_id, tenant_id=g.tenant_id).all()
    return jsonify(envelope(measurement_schema.dump(sheets, many=True)))


@bp.post("/measurement-sheets/<uuid:sheet_id>/verify")
@require_permission("sub:approve")
def verify_measurement_sheet(sheet_id):
    sheet = MeasurementSheet.query.filter_by(id=sheet_id, tenant_id=g.tenant_id).first()
    if not sheet:
        raise APIError("Measurement sheet not found", status=404)
    sheet = services.verify_measurement_sheet(sheet, measured_by=g.user_id)
    return jsonify(measurement_schema.dump(sheet))


# --- Payment certificates (SUB-05, business rules) ------------------------------

@bp.post("/agreements/<uuid:agreement_id>/payment-certificates")
@require_permission("sub:approve")
def issue_payment_certificate(agreement_id):
    agreement = _get_agreement_or_404(agreement_id)
    data = _load(IssuePaymentCertificateSchema())
    certificate = services.issue_payment_certificate(
        g.tenant_id, agreement=agreement, waiver_by=g.user_id, **data
    )
    return jsonify(certificate_schema.dump(certificate)), 201


@bp.get("/agreements/<uuid:agreement_id>/payment-certificates")
@require_permission("sub:read")
def list_payment_certificates(agreement_id):
    _get_agreement_or_404(agreement_id)
    certs = PaymentCertificate.query.filter_by(agreement_id=agreement_id, tenant_id=g.tenant_id).all()
    return jsonify(envelope(certificate_schema.dump(certs, many=True)))


# --- Back charges (SUB-10) -------------------------------------------------------

@bp.post("/agreements/<uuid:agreement_id>/back-charges")
@require_permission("sub:write")
def add_back_charge(agreement_id):
    agreement = _get_agreement_or_404(agreement_id)
    data = _load(BackChargeInputSchema())
    charge = BackCharge(tenant_id=g.tenant_id, agreement_id=agreement.id, raised_by=g.user_id, **data)
    db.session.add(charge)
    db.session.commit()
    return jsonify(back_charge_schema.dump(charge)), 201


@bp.get("/agreements/<uuid:agreement_id>/back-charges")
@require_permission("sub:read")
def list_back_charges(agreement_id):
    _get_agreement_or_404(agreement_id)
    charges = BackCharge.query.filter_by(agreement_id=agreement_id, tenant_id=g.tenant_id).all()
    return jsonify(envelope(back_charge_schema.dump(charges, many=True)))


# --- Retention (SUB-06, business rule) -------------------------------------------

@bp.post("/agreements/<uuid:agreement_id>/retention")
@require_permission("sub:write")
def set_retention(agreement_id):
    agreement = _get_agreement_or_404(agreement_id)
    percentage = request.get_json(force=True).get("percentage", agreement.retention_percentage)
    retention = SubcontractRetention(tenant_id=g.tenant_id, agreement_id=agreement.id, percentage=percentage)
    db.session.add(retention)
    db.session.commit()
    return jsonify(retention_schema.dump(retention)), 201


@bp.get("/agreements/<uuid:agreement_id>/retention")
@require_permission("sub:read")
def list_retention(agreement_id):
    _get_agreement_or_404(agreement_id)
    records = SubcontractRetention.query.filter_by(agreement_id=agreement_id, tenant_id=g.tenant_id).all()
    return jsonify(envelope(retention_schema.dump(records, many=True)))


@bp.post("/retention/<uuid:retention_id>/release")
@require_permission("sub:approve")
def release_retention(retention_id):
    retention = SubcontractRetention.query.filter_by(id=retention_id, tenant_id=g.tenant_id).first()
    if not retention:
        raise APIError("Retention record not found", status=404)
    data = _load(ReleaseRetentionSchema())
    retention = services.release_subcontract_retention(retention, stage=data["stage"], actor_id=g.user_id)
    return jsonify(retention_schema.dump(retention))


# --- Claims (SUB-07) --------------------------------------------------------------

@bp.post("/agreements/<uuid:agreement_id>/claims")
@require_permission("sub:write")
def submit_claim(agreement_id):
    from datetime import datetime, timezone

    agreement = _get_agreement_or_404(agreement_id)
    data = _load(SubcontractClaimInputSchema())
    claim = SubcontractClaim(tenant_id=g.tenant_id, agreement_id=agreement.id, submitted_at=datetime.now(timezone.utc), **data)
    db.session.add(claim)
    db.session.commit()
    return jsonify(claim_schema.dump(claim)), 201


@bp.get("/agreements/<uuid:agreement_id>/claims")
@require_permission("sub:read")
def list_claims(agreement_id):
    _get_agreement_or_404(agreement_id)
    claims = SubcontractClaim.query.filter_by(agreement_id=agreement_id, tenant_id=g.tenant_id).all()
    return jsonify(envelope(claim_schema.dump(claims, many=True)))


@bp.post("/claims/<uuid:claim_id>/review")
@require_permission("sub:approve")
def review_claim(claim_id):
    claim = SubcontractClaim.query.filter_by(id=claim_id, tenant_id=g.tenant_id).first()
    if not claim:
        raise APIError("Claim not found", status=404)
    data = _load(ClaimReviewSchema())
    claim = services.review_claim(claim, decision=data["decision"], reviewed_by=g.user_id, response_notes=data.get("response_notes"))
    return jsonify(claim_schema.dump(claim))


# --- Performance ratings (SUB-08) ----------------------------------------------------

@bp.post("/subcontractors/<uuid:subcontractor_id>/ratings")
@require_permission("sub:write")
def add_performance_rating(subcontractor_id):
    _get_subcontractor_or_404(subcontractor_id)
    data = _load(PerformanceRatingInputSchema())
    rating = services.add_performance_rating(g.tenant_id, subcontractor_id=subcontractor_id, rated_by=g.user_id, **data)
    return jsonify(rating_schema.dump(rating)), 201


@bp.get("/subcontractors/<uuid:subcontractor_id>/ratings")
@require_permission("sub:read")
def list_performance_ratings(subcontractor_id):
    _get_subcontractor_or_404(subcontractor_id)
    ratings = PerformanceRating.query.filter_by(subcontractor_id=subcontractor_id, tenant_id=g.tenant_id).all()
    return jsonify(envelope(rating_schema.dump(ratings, many=True)))


# --- Compliance documents (SUB-09) ------------------------------------------------------

@bp.post("/subcontractors/<uuid:subcontractor_id>/compliance-documents")
@require_permission("sub:write")
def add_compliance_document(subcontractor_id):
    subcontractor = _get_subcontractor_or_404(subcontractor_id)
    data = _load(ComplianceDocumentInputSchema())
    doc = ComplianceDocument(tenant_id=g.tenant_id, subcontractor_id=subcontractor.id, **data)
    db.session.add(doc)
    db.session.commit()
    return jsonify(compliance_schema.dump(doc)), 201


@bp.get("/subcontractors/<uuid:subcontractor_id>/compliance-documents")
@require_permission("sub:read")
def list_compliance_documents(subcontractor_id):
    _get_subcontractor_or_404(subcontractor_id)
    docs = ComplianceDocument.query.filter_by(subcontractor_id=subcontractor_id, tenant_id=g.tenant_id).all()
    return jsonify(envelope(compliance_schema.dump(docs, many=True)))
