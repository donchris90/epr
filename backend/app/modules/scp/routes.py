"""
Module 27 — Subcontractor Portal (Code: SCP)
Flask Blueprint. Base path: /v1/scp
"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.extensions import db
from app.utils.decorators import require_permission
from app.utils.errors import APIError
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
)

bp = Blueprint("scp", __name__, url_prefix="/v1/scp")

user_schema = SubcontractorPortalUserSchema()
progress_schema = ProgressEntrySchema()
certificate_schema = PaymentCertificateSchema()
claim_schema = ClaimSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_portal_user_or_404(portal_user_id) -> SubcontractorPortalUser:
    u = SubcontractorPortalUser.query.filter_by(id=portal_user_id, tenant_id=g.tenant_id).first()
    if not u:
        raise APIError("Subcontractor portal user not found", status=404)
    return u


@bp.get("/health")
def health():
    return jsonify({"module": "scp", "name": "Subcontractor Portal", "status": "ok"})


# --- Portal users --------------------------------------------------------------

@bp.post("/portal-users")
@require_permission("scp:approve")
def create_portal_user():
    data = _load(SubcontractorPortalUserInputSchema())
    user = SubcontractorPortalUser(tenant_id=g.tenant_id, **data)
    db.session.add(user)
    db.session.commit()
    return jsonify(user_schema.dump(user)), 201


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
