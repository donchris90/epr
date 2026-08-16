"""
Module 19 — Project Controls (Code: PC)
SRS Section 4.19 — Flask Blueprint. Base path: /v1/pc
"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.extensions import db
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import envelope

from app.modules.pc import services
from app.modules.pc.models import EVMSnapshot, RiskRegisterEntry
from app.modules.pc.schemas import (
    CreateEVMSnapshotSchema,
    EVMSnapshotSchema,
    GenerateForecastSchema,
    ForecastSchema,
    RiskEntryInputSchema,
    RiskEntrySchema,
    DelayAnalysisInputSchema,
    DelayAnalysisSchema,
    CashFlowForecastInputSchema,
    CashFlowForecastSchema,
)

bp = Blueprint("pc", __name__, url_prefix="/v1/pc")

snapshot_schema = EVMSnapshotSchema()
forecast_schema = ForecastSchema()
risk_schema = RiskEntrySchema()
delay_schema = DelayAnalysisSchema()
cash_flow_schema = CashFlowForecastSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_snapshot_or_404(snapshot_id) -> EVMSnapshot:
    s = EVMSnapshot.query.filter_by(id=snapshot_id, tenant_id=g.tenant_id).first()
    if not s:
        raise APIError("EVM snapshot not found", status=404)
    return s


@bp.get("/health")
def health():
    return jsonify({"module": "pc", "name": "Project Controls", "status": "ok"})


# --- EVM snapshots (PC-01 through PC-05, business rule) --------------------------

@bp.post("/evm-snapshots")
@require_permission("pc:write")
def create_evm_snapshot():
    data = _load(CreateEVMSnapshotSchema())
    snapshot = services.create_evm_snapshot(g.tenant_id, calculated_by=g.user_id, **data)
    return jsonify(snapshot_schema.dump(snapshot)), 201


@bp.get("/evm-snapshots")
@require_permission("pc:read")
def list_evm_snapshots():
    project_id = request.args.get("project_id")
    query = EVMSnapshot.query.filter_by(tenant_id=g.tenant_id)
    if project_id:
        query = query.filter_by(project_id=project_id)
    snapshots = query.order_by(EVMSnapshot.period_end.desc()).all()
    return jsonify(envelope(snapshot_schema.dump(snapshots, many=True)))


@bp.get("/at-risk-projects")
@require_permission("pc:read")
def list_at_risk_projects():
    threshold = request.args.get("threshold", 0.9, type=float)
    projects = services.list_at_risk_projects(g.tenant_id, threshold=threshold)
    return jsonify(envelope(snapshot_schema.dump(projects, many=True)))


# --- Forecast at completion (PC-06) ------------------------------------------------

@bp.post("/evm-snapshots/<uuid:snapshot_id>/forecast")
@require_permission("pc:write")
def generate_forecast(snapshot_id):
    snapshot = _get_snapshot_or_404(snapshot_id)
    data = _load(GenerateForecastSchema())
    forecast = services.generate_forecast(snapshot, **data)
    return jsonify(forecast_schema.dump(forecast)), 201


# --- Risk register (PC-08) ----------------------------------------------------------

@bp.post("/risk-register")
@require_permission("pc:write")
def add_risk_entry():
    data = _load(RiskEntryInputSchema())
    entry = services.add_risk_entry(g.tenant_id, **data)
    return jsonify(risk_schema.dump(entry)), 201


@bp.get("/risk-register")
@require_permission("pc:read")
def list_risk_entries():
    project_id = request.args.get("project_id")
    query = RiskRegisterEntry.query.filter_by(tenant_id=g.tenant_id)
    if project_id:
        query = query.filter_by(project_id=project_id)
    entries = query.all()
    return jsonify(envelope(risk_schema.dump(entries, many=True)))


# --- Delay analysis (PC-09) ----------------------------------------------------------

@bp.post("/delay-analysis")
@require_permission("pc:write")
def summarize_delay_analysis():
    data = _load(DelayAnalysisInputSchema())
    snapshot_id = data.pop("evm_snapshot_id")
    snapshot = _get_snapshot_or_404(snapshot_id)

    summary = services.summarize_delay_analysis(g.tenant_id, snapshot=snapshot, **data)
    return jsonify(delay_schema.dump(summary)), 201


# --- Cash flow forecast (PC-07) -------------------------------------------------------

@bp.post("/cash-flow-forecast")
@require_permission("pc:write")
def generate_cash_flow_forecast():
    data = _load(CashFlowForecastInputSchema())
    forecast = services.generate_project_cash_flow_forecast(g.tenant_id, **data)
    return jsonify(cash_flow_schema.dump(forecast)), 201
