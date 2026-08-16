"""
Module 3 — Estimating & Cost Engineering (Code: EST)
SRS Section 4.3 — Flask Blueprint. Base path: /v1/est
"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.extensions import db
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import get_pagination_params, envelope

from app.modules.est import services
from app.modules.est.models import (
    EstimateVersion,
    BOQItem,
    CostLibraryItem,
    MaterialPrice,
    EquipmentRate,
    LaborRate,
    VendorQuotation,
    CostBreakdownStructure,
    CBSLineItem,
    BudgetRevision,
)
from app.modules.est.schemas import (
    EstimateVersionSchema,
    BOQItemSchema,
    SaveRateAnalysisSchema,
    RateAnalysisSchema,
    CostLibraryItemSchema,
    MaterialPriceSchema,
    EquipmentRateSchema,
    LaborRateSchema,
    VendorQuotationSchema,
    MarkupSchema,
    ContingencyItemSchema,
    CostBreakdownStructureSchema,
    GenerateCBSSchema,
    BudgetRevisionSchema,
)

bp = Blueprint("est", __name__, url_prefix="/v1/est")

estimate_version_schema = EstimateVersionSchema()
boq_item_schema = BOQItemSchema()
rate_analysis_schema = RateAnalysisSchema()
cost_library_item_schema = CostLibraryItemSchema()
material_price_schema = MaterialPriceSchema()
equipment_rate_schema = EquipmentRateSchema()
labor_rate_schema = LaborRateSchema()
vendor_quotation_schema = VendorQuotationSchema()
markup_schema = MarkupSchema()
contingency_item_schema = ContingencyItemSchema()
cbs_schema = CostBreakdownStructureSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_version_or_404(version_id) -> EstimateVersion:
    v = EstimateVersion.query.filter_by(id=version_id, tenant_id=g.tenant_id).first()
    if not v:
        raise APIError("Estimate version not found", status=404)
    return v


def _get_boq_item_or_404(boq_item_id) -> BOQItem:
    item = BOQItem.query.filter_by(id=boq_item_id, tenant_id=g.tenant_id).first()
    if not item:
        raise APIError("BOQ item not found", status=404)
    return item


def _get_cbs_or_404(cbs_id) -> CostBreakdownStructure:
    cbs = CostBreakdownStructure.query.filter_by(id=cbs_id, tenant_id=g.tenant_id).first()
    if not cbs:
        raise APIError("Cost Breakdown Structure not found", status=404)
    return cbs


@bp.get("/health")
def health():
    return jsonify({"module": "est", "name": "Estimating & Cost Engineering", "status": "ok"})


# --- Estimate versions (EST-13, EST-14) -----------------------------------

@bp.post("/estimate-versions")
@require_permission("est:write")
def create_estimate_version():
    data = _load(estimate_version_schema)
    version = services.create_estimate_version(g.tenant_id, **data)
    return jsonify(estimate_version_schema.dump(version)), 201


@bp.get("/tenders/<uuid:tender_id>/estimate-versions")
@require_permission("est:read")
def list_estimate_versions(tender_id):
    versions = EstimateVersion.query.filter_by(tenant_id=g.tenant_id, tender_id=tender_id).order_by(
        EstimateVersion.version_number
    ).all()
    return jsonify(envelope(estimate_version_schema.dump(versions, many=True)))


@bp.post("/estimate-versions/<uuid:version_id>/submit")
@require_permission("est:write")
def submit_estimate_version(version_id):
    version = _get_version_or_404(version_id)
    version = services.submit_estimate_version(version)
    return jsonify(estimate_version_schema.dump(version))


# --- BOQ items (EST-01) ----------------------------------------------------

@bp.post("/estimate-versions/<uuid:version_id>/boq-items")
@require_permission("est:write")
def add_boq_item(version_id):
    version = _get_version_or_404(version_id)
    data = _load(boq_item_schema)
    item = BOQItem(tenant_id=g.tenant_id, estimate_version_id=version.id, **data)
    db.session.add(item)
    db.session.commit()
    return jsonify(boq_item_schema.dump(item)), 201


@bp.get("/estimate-versions/<uuid:version_id>/boq-items")
@require_permission("est:read")
def list_boq_items(version_id):
    _get_version_or_404(version_id)
    items = BOQItem.query.filter_by(estimate_version_id=version_id, tenant_id=g.tenant_id).order_by(
        BOQItem.sort_order
    ).all()
    return jsonify(envelope(boq_item_schema.dump(items, many=True)))


# --- Rate analysis (EST-02, reconciliation business rule) ------------------

@bp.put("/boq-items/<uuid:boq_item_id>/rate-analysis")
@require_permission("est:write")
def save_rate_analysis(boq_item_id):
    boq_item = _get_boq_item_or_404(boq_item_id)
    data = _load(SaveRateAnalysisSchema())
    rate_analysis = services.save_rate_analysis(boq_item, lines=data["lines"], markup_pct=data["markup_pct"])
    return jsonify(rate_analysis_schema.dump(rate_analysis)), 200


@bp.get("/boq-items/<uuid:boq_item_id>/rate-analysis")
@require_permission("est:read")
def get_rate_analysis(boq_item_id):
    boq_item = _get_boq_item_or_404(boq_item_id)
    if not boq_item.rate_analysis:
        raise APIError("No rate analysis recorded for this BOQ item", status=404)
    return jsonify(rate_analysis_schema.dump(boq_item.rate_analysis))


# --- Cost libraries, prices, rates (EST-03 through EST-07) ------------------

@bp.post("/cost-library-items")
@require_permission("est:write")
def create_cost_library_item():
    data = _load(cost_library_item_schema)
    item = CostLibraryItem(tenant_id=g.tenant_id, **data)
    db.session.add(item)
    db.session.commit()
    return jsonify(cost_library_item_schema.dump(item)), 201


@bp.get("/cost-library-items")
@require_permission("est:read")
def list_cost_library_items():
    cursor, limit = get_pagination_params()
    items = CostLibraryItem.query.filter_by(tenant_id=g.tenant_id).order_by(CostLibraryItem.code).limit(limit).all()
    return jsonify(envelope(cost_library_item_schema.dump(items, many=True)))


@bp.post("/material-prices")
@require_permission("est:write")
def create_material_price():
    data = _load(material_price_schema)
    item = MaterialPrice(tenant_id=g.tenant_id, **data)
    db.session.add(item)
    db.session.commit()
    return jsonify(material_price_schema.dump(item)), 201


@bp.get("/material-prices")
@require_permission("est:read")
def list_material_prices():
    query = MaterialPrice.query.filter_by(tenant_id=g.tenant_id)
    material_name = request.args.get("material_name")
    if material_name:
        query = query.filter_by(material_name=material_name)
    items = query.order_by(MaterialPrice.effective_date.desc()).all()
    return jsonify(envelope(material_price_schema.dump(items, many=True)))


@bp.post("/equipment-rates")
@require_permission("est:write")
def create_equipment_rate():
    data = _load(equipment_rate_schema)
    item = EquipmentRate(tenant_id=g.tenant_id, **data)
    db.session.add(item)
    db.session.commit()
    return jsonify(equipment_rate_schema.dump(item)), 201


@bp.get("/equipment-rates")
@require_permission("est:read")
def list_equipment_rates():
    items = EquipmentRate.query.filter_by(tenant_id=g.tenant_id).all()
    return jsonify(envelope(equipment_rate_schema.dump(items, many=True)))


@bp.post("/labor-rates")
@require_permission("est:write")
def create_labor_rate():
    data = _load(labor_rate_schema)
    item = LaborRate(tenant_id=g.tenant_id, **data)
    db.session.add(item)
    db.session.commit()
    return jsonify(labor_rate_schema.dump(item)), 201


@bp.get("/labor-rates")
@require_permission("est:read")
def list_labor_rates():
    items = LaborRate.query.filter_by(tenant_id=g.tenant_id).all()
    return jsonify(envelope(labor_rate_schema.dump(items, many=True)))


@bp.post("/vendor-quotations")
@require_permission("est:write")
def create_vendor_quotation():
    data = _load(vendor_quotation_schema)
    item = VendorQuotation(tenant_id=g.tenant_id, **data)
    db.session.add(item)
    db.session.commit()
    return jsonify(vendor_quotation_schema.dump(item)), 201


@bp.get("/boq-items/<uuid:boq_item_id>/vendor-quotations")
@require_permission("est:read")
def list_vendor_quotations(boq_item_id):
    _get_boq_item_or_404(boq_item_id)
    items = VendorQuotation.query.filter_by(boq_item_id=boq_item_id, tenant_id=g.tenant_id).all()
    return jsonify(envelope(vendor_quotation_schema.dump(items, many=True)))


# --- Markup, contingency, risk allowance (EST-08, EST-09) -------------------

@bp.post("/estimate-versions/<uuid:version_id>/markups")
@require_permission("est:write")
def add_markup(version_id):
    version = _get_version_or_404(version_id)
    data = _load(markup_schema)
    markup = services.set_markup(version, **data)
    return jsonify(markup_schema.dump(markup)), 201


@bp.post("/estimate-versions/<uuid:version_id>/contingency-items")
@require_permission("est:write")
def add_contingency_item(version_id):
    version = _get_version_or_404(version_id)
    data = _load(contingency_item_schema)
    item = services.add_contingency_item(version, **data)
    return jsonify(contingency_item_schema.dump(item)), 201


# --- Engineer's Estimate & Tender Price views (EST-10, EST-11) --------------

@bp.get("/estimate-versions/<uuid:version_id>/engineers-estimate")
@require_permission("est:read")
def get_engineers_estimate(version_id):
    version = _get_version_or_404(version_id)
    total = services.engineers_estimate(version)
    return jsonify({"estimate_version_id": str(version.id), "cost_only_total": str(total)})


@bp.get("/estimate-versions/<uuid:version_id>/tender-price")
@require_permission("est:read")
def get_tender_price(version_id):
    version = _get_version_or_404(version_id)
    return jsonify(services.tender_price_summary(version))


# --- Cost Breakdown Structure & Budget baseline (EST-12) --------------------

@bp.post("/estimate-versions/<uuid:version_id>/generate-cbs")
@require_permission("est:approve")
def generate_cbs(version_id):
    version = _get_version_or_404(version_id)
    data = _load(GenerateCBSSchema())
    cbs = services.generate_cbs_from_estimate(version, project_id=data.get("project_id"))
    return jsonify(cbs_schema.dump(cbs)), 201


@bp.get("/cost-breakdown-structures/<uuid:cbs_id>")
@require_permission("est:read")
def get_cbs(cbs_id):
    cbs = _get_cbs_or_404(cbs_id)
    return jsonify(cbs_schema.dump(cbs))


@bp.post("/cost-breakdown-structures/<uuid:cbs_id>/approve")
@require_permission("est:approve")
def approve_cbs(cbs_id):
    cbs = _get_cbs_or_404(cbs_id)
    cbs = services.approve_cbs(cbs, approver_id=g.user_id)
    return jsonify(cbs_schema.dump(cbs))


@bp.post("/cost-breakdown-structures/<uuid:cbs_id>/budget-revisions")
@require_permission("est:approve")
def create_budget_revision(cbs_id):
    cbs = _get_cbs_or_404(cbs_id)
    data = _load(BudgetRevisionSchema())

    line_item = CBSLineItem.query.filter_by(id=data["cbs_line_item_id"], tenant_id=g.tenant_id, cbs_id=cbs.id).first()
    if not line_item:
        raise APIError("CBS line item not found", status=404)

    revision = services.create_budget_revision(
        cbs, line_item, reason=data["reason"], new_amount=data["revised_amount"], approver_id=g.user_id
    )
    return jsonify(BudgetRevisionSchema().dump(revision)), 201


@bp.post("/budget-revisions/<uuid:revision_id>/finalize")
@require_permission("est:approve")
def finalize_budget_revision(revision_id):
    """Applies a pending budget revision's deferred mutation once its
    governing workflow instance reports approved -- see
    services.py:finalize_budget_revision for what this defers to
    while still pending, and app/workflow/ for the engine itself."""
    revision = BudgetRevision.query.filter_by(id=revision_id, tenant_id=g.tenant_id).first()
    if not revision:
        raise APIError("Budget revision not found", status=404)
    revision = services.finalize_budget_revision(revision, actor_id=g.user_id)
    return jsonify(BudgetRevisionSchema().dump(revision))
