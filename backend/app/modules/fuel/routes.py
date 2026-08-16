"""
Module 10 — Fuel Management (Code: FUEL)
SRS Section 4.10 — Flask Blueprint. Base path: /v1/fuel
"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.extensions import db
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import envelope

from app.modules.fuel import services
from app.modules.fuel.models import FuelTank, FuelPurchase, FuelIssue, FuelBurnRateProfile, TheftFlag
from app.modules.fuel.schemas import (
    FuelTankSchema,
    FuelPurchaseInputSchema,
    FuelPurchaseSchema,
    ReconcileTankSchema,
    FuelIssueInputSchema,
    FuelIssueSchema,
    UsageLogCheckSchema,
    FuelBurnRateProfileSchema,
    FuelVarianceQuerySchema,
    FuelVarianceRecordSchema,
    TheftFlagSchema,
)

bp = Blueprint("fuel", __name__, url_prefix="/v1/fuel")

tank_schema = FuelTankSchema()
purchase_schema = FuelPurchaseSchema()
issue_schema = FuelIssueSchema()
burn_rate_schema = FuelBurnRateProfileSchema()
variance_schema = FuelVarianceRecordSchema()
theft_flag_schema = TheftFlagSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_tank_or_404(tank_id) -> FuelTank:
    t = FuelTank.query.filter_by(id=tank_id, tenant_id=g.tenant_id).first()
    if not t:
        raise APIError("Fuel tank not found", status=404)
    return t


@bp.get("/health")
def health():
    return jsonify({"module": "fuel", "name": "Fuel Management", "status": "ok"})


# --- Tanks (FUEL-02) -----------------------------------------------------------

@bp.post("/tanks")
@require_permission("fuel:write")
def create_tank():
    data = _load(tank_schema)
    tank = FuelTank(tenant_id=g.tenant_id, **data)
    db.session.add(tank)
    db.session.commit()
    return jsonify(tank_schema.dump(tank)), 201


@bp.get("/tanks")
@require_permission("fuel:read")
def list_tanks():
    tanks = FuelTank.query.filter_by(tenant_id=g.tenant_id).all()
    return jsonify(envelope(tank_schema.dump(tanks, many=True)))


@bp.post("/tanks/<uuid:tank_id>/reconcile")
@require_permission("fuel:write")
def reconcile_tank(tank_id):
    tank = _get_tank_or_404(tank_id)
    data = _load(ReconcileTankSchema())
    result = services.reconcile_tank(tank, dip_reading_litres=data["dip_reading_litres"], tolerance_litres=data["tolerance_litres"])
    return jsonify(
        {
            "discrepancy_litres": str(result["discrepancy_litres"]),
            "theft_flag": theft_flag_schema.dump(result["theft_flag"]) if result["theft_flag"] else None,
        }
    )


# --- Purchases (FUEL-01) --------------------------------------------------------

@bp.post("/purchases")
@require_permission("fuel:write")
def create_purchase():
    data = _load(FuelPurchaseInputSchema())
    purchase = services.record_purchase(g.tenant_id, **data)
    return jsonify(purchase_schema.dump(purchase)), 201


@bp.post("/purchases/<uuid:purchase_id>/confirm-delivery")
@require_permission("fuel:write")
def confirm_delivery(purchase_id):
    purchase = FuelPurchase.query.filter_by(id=purchase_id, tenant_id=g.tenant_id).first()
    if not purchase:
        raise APIError("Purchase not found", status=404)
    purchase = services.confirm_delivery(purchase, confirmed_by=g.user_id)
    return jsonify(purchase_schema.dump(purchase))


# --- Issues (FUEL-03, FUEL-09 business rule) --------------------------------------

@bp.post("/issues")
@require_permission("fuel:write")
def create_issue():
    data = _load(FuelIssueInputSchema())
    issue = services.record_issue(g.tenant_id, issued_by=g.user_id, **data)
    return jsonify(issue_schema.dump(issue)), 201


@bp.post("/issues/<uuid:issue_id>/countersign")
@require_permission("fuel:approve")
def countersign_issue(issue_id):
    issue = FuelIssue.query.filter_by(id=issue_id, tenant_id=g.tenant_id).first()
    if not issue:
        raise APIError("Fuel issue not found", status=404)
    issue = services.countersign_issue(issue, countersigned_by=g.user_id)
    return jsonify(issue_schema.dump(issue))


@bp.post("/issues/<uuid:issue_id>/check-usage-log")
@require_permission("fuel:write")
def check_usage_log(issue_id):
    issue = FuelIssue.query.filter_by(id=issue_id, tenant_id=g.tenant_id).first()
    if not issue:
        raise APIError("Fuel issue not found", status=404)
    data = _load(UsageLogCheckSchema())
    flag = services.flag_issue_without_usage_log(issue, has_usage_log=data["has_usage_log"])
    return jsonify(theft_flag_schema.dump(flag) if flag else {"theft_flag": None})


# --- Burn rate profiles & variance (FUEL-04) ---------------------------------------

@bp.post("/burn-rate-profiles")
@require_permission("fuel:write")
def set_burn_rate_profile():
    data = _load(burn_rate_schema)
    profile = FuelBurnRateProfile.query.filter_by(tenant_id=g.tenant_id, equipment_id=data["equipment_id"]).first()
    if profile:
        profile.expected_litres_per_hour = data["expected_litres_per_hour"]
        profile.source = data["source"]
    else:
        profile = FuelBurnRateProfile(tenant_id=g.tenant_id, **data)
        db.session.add(profile)
    db.session.commit()
    return jsonify(burn_rate_schema.dump(profile))


@bp.get("/equipment/<uuid:equipment_id>/variance")
@require_permission("fuel:read")
def get_fuel_variance(equipment_id):
    args = FuelVarianceQuerySchema().load(request.args)
    record = services.calculate_fuel_variance(g.tenant_id, equipment_id=equipment_id, **args)
    return jsonify(variance_schema.dump(record))


@bp.post("/variance-records/<uuid:record_id>/check-theft")
@require_permission("fuel:write")
def check_variance_theft(record_id):
    from app.modules.fuel.models import FuelVarianceRecord

    record = FuelVarianceRecord.query.filter_by(id=record_id, tenant_id=g.tenant_id).first()
    if not record:
        raise APIError("Variance record not found", status=404)

    threshold_pct = request.args.get("threshold_pct", 15, type=float)
    flag = services.check_variance_theft_flag(record, threshold_pct=threshold_pct)
    return jsonify(theft_flag_schema.dump(flag) if flag else {"theft_flag": None})


@bp.get("/equipment/<uuid:equipment_id>/cost-breakdown")
@require_permission("fuel:read")
def get_fuel_cost_breakdown(equipment_id):
    args = FuelVarianceQuerySchema().load(request.args)
    result = services.fuel_cost_breakdown(g.tenant_id, equipment_id=equipment_id, **args)
    return jsonify({k: str(v) for k, v in result.items()})


# --- Theft flags (FUEL-05, business rule) --------------------------------------------

@bp.get("/theft-flags")
@require_permission("fuel:read")
def list_theft_flags():
    status = request.args.get("status")
    query = TheftFlag.query.filter_by(tenant_id=g.tenant_id)
    if status:
        query = query.filter_by(status=status)
    flags = query.all()
    return jsonify(envelope(theft_flag_schema.dump(flags, many=True)))


@bp.post("/theft-flags/escalate-unresolved")
@require_permission("fuel:write")
def escalate_unresolved_theft_flags():
    threshold_days = request.args.get("threshold_days", 7, type=int)
    escalated = services.escalate_unresolved_theft_flags(g.tenant_id, threshold_days=threshold_days)
    return jsonify(envelope(theft_flag_schema.dump(escalated, many=True)))
