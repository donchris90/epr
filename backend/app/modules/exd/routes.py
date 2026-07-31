"""
Module 21 — Executive Dashboard (Code: EXD)
SRS Section 4.21 — Flask Blueprint. Base path: /v1/exd
"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.extensions import db
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import envelope

from app.modules.exd import services
from app.modules.exd.models import DashboardWidget, DashboardConfiguration
from app.modules.exd.schemas import (
    DashboardWidgetInputSchema,
    DashboardWidgetSchema,
    DashboardConfigurationInputSchema,
    DashboardConfigurationSchema,
    CompanyRevenueQuerySchema,
    EquipmentUtilizationQuerySchema,
)

bp = Blueprint("exd", __name__, url_prefix="/v1/exd")

widget_schema = DashboardWidgetSchema()
config_schema = DashboardConfigurationSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _decimalish(value):
    return str(value) if value is not None else None


@bp.get("/health")
def health():
    return jsonify({"module": "exd", "name": "Executive Dashboard", "status": "ok"})


# --- Widgets & configuration (EXD-12) --------------------------------------------

@bp.post("/widgets")
@require_permission("exd:approve")
def create_widget():
    data = _load(DashboardWidgetInputSchema())
    widget = DashboardWidget(tenant_id=g.tenant_id, **data)
    db.session.add(widget)
    db.session.commit()
    return jsonify(widget_schema.dump(widget)), 201


@bp.get("/widgets")
@require_permission("exd:read")
def list_widgets():
    widgets = DashboardWidget.query.filter_by(tenant_id=g.tenant_id).all()
    return jsonify(envelope(widget_schema.dump(widgets, many=True)))


@bp.post("/configurations")
@require_permission("exd:approve")
def create_configuration():
    data = _load(DashboardConfigurationInputSchema())
    data["widget_ids"] = [str(w) for w in data["widget_ids"]]
    if data.get("region_project_ids"):
        data["region_project_ids"] = [str(p) for p in data["region_project_ids"]]
    config = DashboardConfiguration(tenant_id=g.tenant_id, **data)
    db.session.add(config)
    db.session.commit()
    return jsonify(config_schema.dump(config)), 201


@bp.get("/configurations/<string:role_name>")
@require_permission("exd:read")
def get_configuration(role_name):
    config = DashboardConfiguration.query.filter_by(tenant_id=g.tenant_id, role_name=role_name).first()
    if not config:
        raise APIError("No dashboard configuration for this role", status=404)
    return jsonify(config_schema.dump(config))


# --- Company Revenue vs Budget (EXD-01) --------------------------------------------

@bp.get("/company-revenue")
@require_permission("exd:read")
def get_company_revenue():
    args = CompanyRevenueQuerySchema().load(request.args)
    result = services.get_company_revenue(g.tenant_id, **args)
    return jsonify(
        {
            "actual_revenue": _decimalish(result["actual_revenue"]),
            "budget_amount": _decimalish(result.get("budget_amount")),
            "variance": _decimalish(result.get("variance")),
            "variance_pct": _decimalish(result.get("variance_pct")),
            "drill_down_journal_entries": result["drill_down_journal_entries"],
        }
    )


# --- Active Projects: CPI/SPI (EXD-06, EXD-12 role scoping) ------------------------

@bp.get("/active-projects-performance")
@require_permission("exd:read")
def get_active_projects_performance():
    """EXD-12: if a `role` query param is given and that role has a
    DashboardConfiguration with `region_project_ids` set, results are
    filtered to that region -- a Regional Director's role sees only
    their region; a role with no configuration (or an unscoped one,
    region_project_ids=null) sees the full consolidation."""
    results = services.get_active_projects_performance(g.tenant_id)

    role = request.args.get("role")
    if role:
        config = DashboardConfiguration.query.filter_by(tenant_id=g.tenant_id, role_name=role).first()
        if config and config.region_project_ids is not None:
            allowed = set(config.region_project_ids)
            results = [r for r in results if r["project_id"] in allowed]

    return jsonify(
        envelope(
            [
                {**r, "cpi": _decimalish(r["cpi"]), "spi": _decimalish(r["spi"])}
                for r in results
            ]
        )
    )


# --- Consolidated Project Risks (EXD-11) --------------------------------------------

@bp.get("/project-risks")
@require_permission("exd:read")
def get_project_risks():
    status = request.args.get("status", "open")
    risks = services.get_consolidated_project_risks(g.tenant_id, status=status)
    return jsonify(envelope([{**r, "exposure_value": _decimalish(r["exposure_value"])} for r in risks]))


# --- AR / AP Aging (EXD-08) -----------------------------------------------------------

@bp.get("/ar-ap-aging")
@require_permission("exd:read")
def get_ar_ap_aging():
    result = services.get_ar_ap_aging_summary(g.tenant_id)
    return jsonify(result)


# --- Equipment Utilization by category (EXD-04) -----------------------------------------

@bp.get("/equipment-utilization")
@require_permission("exd:read")
def get_equipment_utilization():
    args = EquipmentUtilizationQuerySchema().load(request.args)
    result = services.get_equipment_utilization_by_category(g.tenant_id, **args)
    return jsonify(
        envelope(
            [
                {
                    "ownership_type": r["ownership_type"],
                    "hours_operated": str(r["hours_operated"]),
                    "hours_scheduled": str(r["hours_scheduled"]),
                    "utilization_pct": _decimalish(r["utilization_pct"]),
                }
                for r in result
            ]
        )
    )
