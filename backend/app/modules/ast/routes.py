"""
Module 20 — Asset Management (Code: AST)
SRS Section 4.20 — Flask Blueprint. Base path: /v1/ast
"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.extensions import db
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import envelope

from app.modules.ast import services
from app.modules.ast.models import (
    Asset,
    MaintenanceSchedule,
    AssetInspection,
    WarrantyRecord,
    DefectsLiabilityRecord,
    DefectItem,
    LifecycleCostRecord,
)
from app.modules.ast.schemas import (
    AssetInputSchema,
    UpdateAssetAttributesSchema,
    AssetSchema,
    MaintenanceScheduleInputSchema,
    MaintenanceScheduleSchema,
    AssetInspectionInputSchema,
    AssetInspectionSchema,
    WarrantyRecordInputSchema,
    WarrantyRecordSchema,
    DLPRecordInputSchema,
    DLPRecordSchema,
    DefectItemInputSchema,
    DefectItemSchema,
    LifecycleCostInputSchema,
    LifecycleCostSchema,
)

bp = Blueprint("ast", __name__, url_prefix="/v1/ast")

asset_schema = AssetSchema()
schedule_schema = MaintenanceScheduleSchema()
inspection_schema = AssetInspectionSchema()
warranty_schema = WarrantyRecordSchema()
dlp_schema = DLPRecordSchema()
defect_schema = DefectItemSchema()
lifecycle_cost_schema = LifecycleCostSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_asset_or_404(asset_id) -> Asset:
    a = Asset.query.filter_by(id=asset_id, tenant_id=g.tenant_id).first()
    if not a:
        raise APIError("Asset not found", status=404)
    return a


def _get_schedule_or_404(schedule_id) -> MaintenanceSchedule:
    s = MaintenanceSchedule.query.filter_by(id=schedule_id, tenant_id=g.tenant_id).first()
    if not s:
        raise APIError("Maintenance schedule not found", status=404)
    return s


def _get_dlp_or_404(dlp_id) -> DefectsLiabilityRecord:
    d = DefectsLiabilityRecord.query.filter_by(id=dlp_id, tenant_id=g.tenant_id).first()
    if not d:
        raise APIError("Defects liability record not found", status=404)
    return d


def _get_defect_or_404(defect_id) -> DefectItem:
    d = DefectItem.query.filter_by(id=defect_id, tenant_id=g.tenant_id).first()
    if not d:
        raise APIError("Defect item not found", status=404)
    return d


@bp.get("/health")
def health():
    return jsonify({"module": "ast", "name": "Asset Management", "status": "ok"})


# --- Assets (AST-01, AST-02, AST-08, business rule) -------------------------------

@bp.post("/assets")
@require_permission("ast:write")
def create_asset():
    data = _load(AssetInputSchema())
    asset = Asset(tenant_id=g.tenant_id, **data)
    db.session.add(asset)
    db.session.commit()
    return jsonify(asset_schema.dump(asset)), 201


@bp.get("/assets")
@require_permission("ast:read")
def list_assets():
    category = request.args.get("category")
    query = Asset.query.filter_by(tenant_id=g.tenant_id)
    if category:
        query = query.filter_by(asset_category=category)
    assets = query.all()
    return jsonify(envelope(asset_schema.dump(assets, many=True)))


@bp.get("/assets/<uuid:asset_id>")
@require_permission("ast:read")
def get_asset(asset_id):
    return jsonify(asset_schema.dump(_get_asset_or_404(asset_id)))


@bp.put("/assets/<uuid:asset_id>/attributes")
@require_permission("ast:write")
def update_asset_attributes(asset_id):
    """Business rule: this is the ONLY update route for an asset, and
    it deliberately cannot touch baseline_data/as_built_record_id/
    handover_date -- the schema simply has no fields for them."""
    asset = _get_asset_or_404(asset_id)
    data = _load(UpdateAssetAttributesSchema())
    asset = services.update_asset_attributes(asset, **data)
    return jsonify(asset_schema.dump(asset))


# --- Maintenance schedules (AST-03) -----------------------------------------------

@bp.post("/assets/<uuid:asset_id>/maintenance-schedules")
@require_permission("ast:write")
def create_maintenance_schedule(asset_id):
    asset = _get_asset_or_404(asset_id)
    data = _load(MaintenanceScheduleInputSchema())
    schedule = MaintenanceSchedule(tenant_id=g.tenant_id, asset_id=asset.id, **data)
    db.session.add(schedule)
    db.session.commit()
    return jsonify(schedule_schema.dump(schedule)), 201


@bp.post("/maintenance-schedules/<uuid:schedule_id>/complete")
@require_permission("ast:write")
def complete_maintenance_task(schedule_id):
    schedule = _get_schedule_or_404(schedule_id)
    schedule = services.complete_maintenance_task(schedule)
    return jsonify(schedule_schema.dump(schedule))


@bp.get("/maintenance-schedules/overdue")
@require_permission("ast:read")
def list_overdue_maintenance():
    overdue = services.list_overdue_maintenance(g.tenant_id)
    return jsonify(envelope(schedule_schema.dump(overdue, many=True)))


# --- Asset inspections (AST-04) ----------------------------------------------------

@bp.post("/assets/<uuid:asset_id>/inspections")
@require_permission("ast:write")
def create_inspection(asset_id):
    asset = _get_asset_or_404(asset_id)
    data = _load(AssetInspectionInputSchema())
    inspection = AssetInspection(tenant_id=g.tenant_id, asset_id=asset.id, **data)
    db.session.add(inspection)
    db.session.commit()
    return jsonify(inspection_schema.dump(inspection)), 201


@bp.get("/assets/<uuid:asset_id>/inspections")
@require_permission("ast:read")
def list_inspections(asset_id):
    _get_asset_or_404(asset_id)
    inspections = AssetInspection.query.filter_by(asset_id=asset_id, tenant_id=g.tenant_id).all()
    return jsonify(envelope(inspection_schema.dump(inspections, many=True)))


# --- Warranty records (AST-05) ------------------------------------------------------

@bp.post("/assets/<uuid:asset_id>/warranties")
@require_permission("ast:write")
def create_warranty(asset_id):
    asset = _get_asset_or_404(asset_id)
    data = _load(WarrantyRecordInputSchema())
    warranty = WarrantyRecord(tenant_id=g.tenant_id, asset_id=asset.id, **data)
    db.session.add(warranty)
    db.session.commit()
    return jsonify(warranty_schema.dump(warranty)), 201


@bp.get("/warranties/expiring")
@require_permission("ast:read")
def list_expiring_warranties():
    from datetime import date, timedelta

    within_days = request.args.get("within_days", 30, type=int)
    horizon = date.today() + timedelta(days=within_days)
    warranties = WarrantyRecord.query.filter(
        WarrantyRecord.tenant_id == g.tenant_id,
        WarrantyRecord.valid_until.isnot(None),
        WarrantyRecord.valid_until <= horizon,
    ).all()
    return jsonify(envelope(warranty_schema.dump(warranties, many=True)))


# --- Defects Liability Period (AST-06, business rule) -------------------------------

@bp.post("/assets/<uuid:asset_id>/dlp")
@require_permission("ast:write")
def create_dlp_record(asset_id):
    asset = _get_asset_or_404(asset_id)
    data = _load(DLPRecordInputSchema())
    dlp = DefectsLiabilityRecord(tenant_id=g.tenant_id, asset_id=asset.id, **data)
    db.session.add(dlp)
    db.session.commit()
    return jsonify(dlp_schema.dump(dlp)), 201


@bp.post("/dlp/<uuid:dlp_id>/defects")
@require_permission("ast:write")
def add_defect(dlp_id):
    dlp = _get_dlp_or_404(dlp_id)
    data = _load(DefectItemInputSchema())
    defect = DefectItem(tenant_id=g.tenant_id, dlp_record_id=dlp.id, **data)
    db.session.add(defect)
    db.session.commit()
    return jsonify(defect_schema.dump(defect)), 201


@bp.post("/defects/<uuid:defect_id>/resolve")
@require_permission("ast:write")
def resolve_defect(defect_id):
    defect = _get_defect_or_404(defect_id)
    defect = services.resolve_defect(defect)
    return jsonify(defect_schema.dump(defect))


@bp.post("/defects/<uuid:defect_id>/verify")
@require_permission("ast:approve")
def verify_defect(defect_id):
    defect = _get_defect_or_404(defect_id)
    defect = services.verify_defect(defect, verified_by=g.user_id)
    return jsonify(defect_schema.dump(defect))


@bp.post("/dlp/<uuid:dlp_id>/release-retention")
@require_permission("ast:approve")
def release_dlp_retention(dlp_id):
    dlp = _get_dlp_or_404(dlp_id)
    dlp = services.release_dlp_retention(dlp)
    return jsonify(dlp_schema.dump(dlp))


# --- Lifecycle cost (AST-07) -----------------------------------------------------------

@bp.post("/assets/<uuid:asset_id>/lifecycle-costs")
@require_permission("ast:write")
def add_lifecycle_cost(asset_id):
    asset = _get_asset_or_404(asset_id)
    data = _load(LifecycleCostInputSchema())
    record = LifecycleCostRecord(tenant_id=g.tenant_id, asset_id=asset.id, **data)
    db.session.add(record)
    db.session.commit()
    return jsonify(lifecycle_cost_schema.dump(record)), 201


@bp.get("/assets/<uuid:asset_id>/lifecycle-cost-summary")
@require_permission("ast:read")
def get_lifecycle_cost_summary(asset_id):
    _get_asset_or_404(asset_id)
    result = services.get_lifecycle_cost_summary(g.tenant_id, asset_id=asset_id)
    return jsonify({"breakdown": {k: str(v) for k, v in result["breakdown"].items()}, "total": str(result["total"])})
