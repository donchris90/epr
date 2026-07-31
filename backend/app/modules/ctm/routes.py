"""
Module 4 — Contract Management (Code: CTM)
SRS Section 4.4 — Flask Blueprint. Base path: /v1/ctm
"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.extensions import db
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import get_pagination_params, envelope

from app.modules.ctm import services
from app.modules.ctm.models import (
    Contract,
    ContractDocument,
    PaymentTerm,
    PerformanceBond,
    AdvancePayment,
    Retention,
    Insurance,
    Guarantee,
    ContractAmendment,
)
from app.modules.ctm.schemas import (
    ContractSchema,
    ContractDocumentSchema,
    PaymentTermSchema,
    PerformanceBondSchema,
    AdvancePaymentSchema,
    ApplyCertificateSchema,
    RetentionSchema,
    ReleaseRetentionSchema,
    InsuranceSchema,
    GuaranteeSchema,
    ContractAmendmentSchema,
)

bp = Blueprint("ctm", __name__, url_prefix="/v1/ctm")

contract_schema = ContractSchema()
document_schema = ContractDocumentSchema()
payment_term_schema = PaymentTermSchema()
bond_schema = PerformanceBondSchema()
advance_schema = AdvancePaymentSchema()
retention_schema = RetentionSchema()
insurance_schema = InsuranceSchema()
guarantee_schema = GuaranteeSchema()
amendment_schema = ContractAmendmentSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_contract_or_404(contract_id) -> Contract:
    c = Contract.query.filter_by(id=contract_id, tenant_id=g.tenant_id, deleted_at=None).first()
    if not c:
        raise APIError("Contract not found", status=404)
    return c


@bp.get("/health")
def health():
    return jsonify({"module": "ctm", "name": "Contract Management", "status": "ok"})


# --- Contracts & the award orchestration (CTM-01) ---------------------------

@bp.get("/contracts")
@require_permission("ctm:read")
def list_contracts():
    cursor, limit = get_pagination_params()
    items = Contract.query.filter_by(tenant_id=g.tenant_id, deleted_at=None).limit(limit).all()
    return jsonify(envelope(contract_schema.dump(items, many=True)))


@bp.get("/contracts/<uuid:contract_id>")
@require_permission("ctm:read")
def get_contract(contract_id):
    return jsonify(contract_schema.dump(_get_contract_or_404(contract_id)))


@bp.post("/contracts/award")
@require_permission("ctm:write")
def award_contract():
    """
    Orchestrates contract award: creates the Contract (CTM-01), then
    calls back into Module 1 to link it to the winning Opportunity and
    transition it to "won" -- this is the single call that closes the
    loop left open by BDC's and TBM's business rules. Requires
    `opportunity_id` in addition to the usual Contract fields, since
    that's what identifies which Opportunity to mark won.
    """
    body = request.get_json(force=True) or {}
    opportunity_id = body.pop("opportunity_id", None)
    if not opportunity_id:
        raise APIError("opportunity_id is required", status=400)

    data = _load(contract_schema)
    contract = services.create_contract_on_award(g.tenant_id, **data)

    from app.modules.bdc.models import Opportunity
    from app.modules.bdc import services as bdc_services

    opportunity = Opportunity.query.filter_by(id=opportunity_id, tenant_id=g.tenant_id).first()
    if not opportunity:
        raise APIError("Opportunity not found", status=404, detail="Contract was created but not linked.")

    opportunity = bdc_services.link_contract_and_mark_won(opportunity, contract_id=contract.id, actor_id=g.user_id)

    return jsonify({"contract": contract_schema.dump(contract), "opportunity_stage": opportunity.stage}), 201


# --- Contract documents (CTM-03) --------------------------------------------

@bp.post("/contracts/<uuid:contract_id>/documents")
@require_permission("ctm:write")
def add_document(contract_id):
    contract = _get_contract_or_404(contract_id)
    data = _load(document_schema)
    doc = ContractDocument(tenant_id=g.tenant_id, contract_id=contract.id, **data)
    db.session.add(doc)
    db.session.commit()
    return jsonify(document_schema.dump(doc)), 201


# --- Payment terms (CTM-02) --------------------------------------------------

@bp.post("/contracts/<uuid:contract_id>/payment-terms")
@require_permission("ctm:write")
def add_payment_term(contract_id):
    contract = _get_contract_or_404(contract_id)
    data = _load(payment_term_schema)
    term = PaymentTerm(tenant_id=g.tenant_id, contract_id=contract.id, **data)
    db.session.add(term)
    db.session.commit()
    return jsonify(payment_term_schema.dump(term)), 201


# --- Performance bonds (CTM-04) ----------------------------------------------

@bp.post("/contracts/<uuid:contract_id>/performance-bonds")
@require_permission("ctm:write")
def add_performance_bond(contract_id):
    contract = _get_contract_or_404(contract_id)
    data = _load(bond_schema)
    bond = PerformanceBond(tenant_id=g.tenant_id, contract_id=contract.id, **data)
    db.session.add(bond)
    db.session.commit()
    return jsonify(bond_schema.dump(bond)), 201


# --- Advance payments (CTM-05) -----------------------------------------------

@bp.post("/contracts/<uuid:contract_id>/advance-payments")
@require_permission("ctm:write")
def add_advance_payment(contract_id):
    contract = _get_contract_or_404(contract_id)
    data = _load(advance_schema)
    advance = AdvancePayment(tenant_id=g.tenant_id, contract_id=contract.id, **data)
    db.session.add(advance)
    db.session.commit()
    return jsonify(advance_schema.dump(advance)), 201


@bp.post("/advance-payments/<uuid:advance_id>/apply-to-certificate")
@require_permission("ctm:write")
def apply_advance_recoupment(advance_id):
    advance = AdvancePayment.query.filter_by(id=advance_id, tenant_id=g.tenant_id).first()
    if not advance:
        raise APIError("Advance payment not found", status=404)

    data = _load(ApplyCertificateSchema())
    recouped = services.apply_advance_recoupment_to_certificate(advance, certificate_amount=data["certificate_amount"])
    return jsonify({"recouped_this_certificate": str(recouped), "advance_payment": advance_schema.dump(advance)})


# --- Retention (CTM-06, business rule) ---------------------------------------

@bp.post("/contracts/<uuid:contract_id>/retention")
@require_permission("ctm:write")
def set_retention(contract_id):
    contract = _get_contract_or_404(contract_id)
    data = _load(retention_schema)
    retention = Retention(tenant_id=g.tenant_id, contract_id=contract.id, **data)
    db.session.add(retention)
    db.session.commit()
    return jsonify(retention_schema.dump(retention)), 201


@bp.post("/retention/<uuid:retention_id>/apply-to-certificate")
@require_permission("ctm:write")
def apply_retention(retention_id):
    retention = Retention.query.filter_by(id=retention_id, tenant_id=g.tenant_id).first()
    if not retention:
        raise APIError("Retention record not found", status=404)

    data = _load(ApplyCertificateSchema())
    withheld = services.apply_retention_to_certificate(retention, certificate_amount=data["certificate_amount"])
    return jsonify({"withheld_this_certificate": str(withheld), "retention": retention_schema.dump(retention)})


@bp.post("/retention/<uuid:retention_id>/release")
@require_permission("ctm:approve")
def release_retention(retention_id):
    retention = Retention.query.filter_by(id=retention_id, tenant_id=g.tenant_id).first()
    if not retention:
        raise APIError("Retention record not found", status=404)

    data = _load(ReleaseRetentionSchema())
    retention = services.release_retention(retention, stage=data["stage"], actor_id=g.user_id)
    return jsonify(retention_schema.dump(retention))


# --- Insurance (CTM-07) -------------------------------------------------------

@bp.post("/contracts/<uuid:contract_id>/insurances")
@require_permission("ctm:write")
def add_insurance(contract_id):
    contract = _get_contract_or_404(contract_id)
    data = _load(insurance_schema)
    insurance = Insurance(tenant_id=g.tenant_id, contract_id=contract.id, **data)
    db.session.add(insurance)
    db.session.commit()
    return jsonify(insurance_schema.dump(insurance)), 201


# --- Guarantees (CTM-08) -------------------------------------------------------

@bp.post("/contracts/<uuid:contract_id>/guarantees")
@require_permission("ctm:write")
def add_guarantee(contract_id):
    contract = _get_contract_or_404(contract_id)
    data = _load(guarantee_schema)
    guarantee = Guarantee(tenant_id=g.tenant_id, contract_id=contract.id, **data)
    db.session.add(guarantee)
    db.session.commit()
    return jsonify(guarantee_schema.dump(guarantee)), 201


# --- Amendments (CTM-09, CTM-10) -----------------------------------------------

@bp.post("/contracts/<uuid:contract_id>/amendments")
@require_permission("ctm:approve")
def add_amendment(contract_id):
    contract = _get_contract_or_404(contract_id)
    data = _load(amendment_schema)
    amendment_type = data.pop("amendment_type")
    description = data.pop("description")
    amendment = services.record_amendment(
        contract, amendment_type=amendment_type, description=description, actor_id=g.user_id, **data
    )
    return jsonify(amendment_schema.dump(amendment)), 201


# --- Expiry alerts (CTM-04/07/08, business rule) --------------------------------

@bp.get("/expiring-instruments")
@require_permission("ctm:read")
def expiring_instruments():
    within_days = request.args.get("within_days", 30, type=int)
    result = services.expiring_instruments(g.tenant_id, within_days=within_days)
    return jsonify(
        {
            "performance_bonds": bond_schema.dump(result["performance_bonds"], many=True),
            "insurances": insurance_schema.dump(result["insurances"], many=True),
            "guarantees": guarantee_schema.dump(result["guarantees"], many=True),
        }
    )
