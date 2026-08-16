"""
Module 16 — Plant & Quarry Management (Code: PQ)
SRS Section 4.16 — Flask Blueprint. Base path: /v1/pq
"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.extensions import db
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import envelope

from app.modules.pq import services
from app.modules.pq.models import (
    CrusherProductionRecord,
    AsphaltPlantBatch,
    ConcretePlantBatch,
    QuarryProductionRecord,
    Stockpile,
    ExplosivesRegister,
    DrillingRecord,
    BlastingRecord,
    HaulageRecord,
)
from app.modules.pq.schemas import (
    CrusherProductionInputSchema,
    CrusherProductionSchema,
    AsphaltBatchInputSchema,
    AsphaltBatchSchema,
    ConcreteBatchInputSchema,
    ConcreteBatchSchema,
    QuarryProductionInputSchema,
    QuarryProductionSchema,
    StockpileInputSchema,
    ReconcileStockpileSchema,
    StockpileSchema,
    ExplosivesEntryInputSchema,
    ExplosivesEntrySchema,
    ExplosivesCorrectionInputSchema,
    ExplosivesCorrectionSchema,
    DrillingRecordInputSchema,
    DrillingRecordSchema,
    BlastingRecordInputSchema,
    MarkBlastCompleteSchema,
    BlastingRecordSchema,
    HaulageRecordInputSchema,
    HaulageRecordSchema,
    ProductionReportInputSchema,
    ProductionReportSchema,
)

bp = Blueprint("pq", __name__, url_prefix="/v1/pq")

crusher_schema = CrusherProductionSchema()
asphalt_schema = AsphaltBatchSchema()
concrete_schema = ConcreteBatchSchema()
quarry_schema = QuarryProductionSchema()
stockpile_schema = StockpileSchema()
explosives_schema = ExplosivesEntrySchema()
correction_schema = ExplosivesCorrectionSchema()
drilling_schema = DrillingRecordSchema()
blasting_schema = BlastingRecordSchema()
haulage_schema = HaulageRecordSchema()
report_schema = ProductionReportSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_stockpile_or_404(stockpile_id) -> Stockpile:
    s = Stockpile.query.filter_by(id=stockpile_id, tenant_id=g.tenant_id).first()
    if not s:
        raise APIError("Stockpile not found", status=404)
    return s


def _get_explosives_entry_or_404(entry_id) -> ExplosivesRegister:
    e = ExplosivesRegister.query.filter_by(id=entry_id, tenant_id=g.tenant_id).first()
    if not e:
        raise APIError("Explosives register entry not found", status=404)
    return e


def _get_blast_or_404(blast_id) -> BlastingRecord:
    b = BlastingRecord.query.filter_by(id=blast_id, tenant_id=g.tenant_id).first()
    if not b:
        raise APIError("Blasting record not found", status=404)
    return b


@bp.get("/health")
def health():
    return jsonify({"module": "pq", "name": "Plant & Quarry Management", "status": "ok"})


# --- Crusher production (PQ-01) ---------------------------------------------------

@bp.post("/crusher-production")
@require_permission("pq:write")
def create_crusher_production():
    data = _load(CrusherProductionInputSchema())
    record = CrusherProductionRecord(tenant_id=g.tenant_id, **data)
    db.session.add(record)
    db.session.commit()
    return jsonify(crusher_schema.dump(record)), 201


# --- Asphalt plant batches (PQ-02) -----------------------------------------------

@bp.post("/asphalt-batches")
@require_permission("pq:write")
def create_asphalt_batch():
    data = _load(AsphaltBatchInputSchema())
    batch = AsphaltPlantBatch(tenant_id=g.tenant_id, **data)
    db.session.add(batch)
    db.session.commit()
    return jsonify(asphalt_schema.dump(batch)), 201


# --- Concrete plant batches (PQ-03) -----------------------------------------------

@bp.post("/concrete-batches")
@require_permission("pq:write")
def create_concrete_batch():
    data = _load(ConcreteBatchInputSchema())
    batch = ConcretePlantBatch(tenant_id=g.tenant_id, **data)
    db.session.add(batch)
    db.session.commit()
    return jsonify(concrete_schema.dump(batch)), 201


# --- Quarry production (PQ-04) ----------------------------------------------------

@bp.post("/quarry-production")
@require_permission("pq:write")
def create_quarry_production():
    data = _load(QuarryProductionInputSchema())
    record = QuarryProductionRecord(tenant_id=g.tenant_id, **data)
    db.session.add(record)
    db.session.commit()
    return jsonify(quarry_schema.dump(record)), 201


# --- Stockpiles (PQ-05) -------------------------------------------------------------

@bp.post("/stockpiles")
@require_permission("pq:write")
def create_stockpile():
    data = _load(StockpileInputSchema())
    stockpile = Stockpile(tenant_id=g.tenant_id, **data)
    db.session.add(stockpile)
    db.session.commit()
    return jsonify(stockpile_schema.dump(stockpile)), 201


@bp.get("/stockpiles")
@require_permission("pq:read")
def list_stockpiles():
    stockpiles = Stockpile.query.filter_by(tenant_id=g.tenant_id).all()
    return jsonify(envelope(stockpile_schema.dump(stockpiles, many=True)))


@bp.post("/stockpiles/<uuid:stockpile_id>/reconcile")
@require_permission("pq:write")
def reconcile_stockpile(stockpile_id):
    stockpile = _get_stockpile_or_404(stockpile_id)
    data = _load(ReconcileStockpileSchema())
    result = services.reconcile_stockpile(stockpile, **data)
    return jsonify({"discrepancy": str(result["discrepancy"]), "quantity_after": str(result["quantity_after"])})


# --- Explosives register (PQ-06, business rule) ------------------------------------
# NOTE: deliberately NO PUT/PATCH/DELETE route for explosives entries.
# The only way to record a change after the fact is the correction
# endpoint below, which adds a new row rather than mutating this one.

@bp.post("/explosives-register")
@require_permission("pq:write")
def create_explosives_entry():
    data = _load(ExplosivesEntryInputSchema())
    entry = ExplosivesRegister(tenant_id=g.tenant_id, recorded_by=g.user_id, **data)
    db.session.add(entry)
    db.session.commit()
    return jsonify(explosives_schema.dump(entry)), 201


@bp.get("/explosives-register")
@require_permission("pq:read")
def list_explosives_entries():
    material_type = request.args.get("material_type")
    query = ExplosivesRegister.query.filter_by(tenant_id=g.tenant_id)
    if material_type:
        query = query.filter_by(material_type=material_type)
    entries = query.all()
    return jsonify(envelope(explosives_schema.dump(entries, many=True)))


@bp.post("/explosives-register/<uuid:entry_id>/corrections")
@require_permission("pq:approve")
def correct_explosives_entry(entry_id):
    entry = _get_explosives_entry_or_404(entry_id)
    data = _load(ExplosivesCorrectionInputSchema())
    correction = services.correct_explosives_entry(entry, corrected_by=g.user_id, **data)
    return jsonify(correction_schema.dump(correction)), 201


@bp.get("/explosives-register/balance")
@require_permission("pq:read")
def get_explosives_balance():
    material_type = request.args.get("material_type")
    if not material_type:
        raise APIError("material_type query parameter is required", status=400)
    balance = services.get_explosives_balance(g.tenant_id, material_type=material_type)
    return jsonify({"material_type": material_type, "balance": str(balance)})


# --- Drilling & blasting (PQ-07, PQ-08, business rule) ---------------------------------

@bp.post("/drilling-records")
@require_permission("pq:write")
def create_drilling_record():
    data = _load(DrillingRecordInputSchema())
    record = DrillingRecord(tenant_id=g.tenant_id, **data)
    db.session.add(record)
    db.session.commit()
    return jsonify(drilling_schema.dump(record)), 201


@bp.post("/blasting-records")
@require_permission("pq:write")
def create_blasting_record():
    data = _load(BlastingRecordInputSchema())
    drilling = DrillingRecord.query.filter_by(id=data["drilling_record_id"], tenant_id=g.tenant_id).first()
    if not drilling:
        raise APIError("Linked drilling record not found", status=404)

    blast = BlastingRecord(tenant_id=g.tenant_id, **data)
    db.session.add(blast)
    db.session.commit()
    return jsonify(blasting_schema.dump(blast)), 201


@bp.post("/blasting-records/<uuid:blast_id>/mark-complete")
@require_permission("pq:approve")
def mark_blast_complete(blast_id):
    blast = _get_blast_or_404(blast_id)
    data = _load(MarkBlastCompleteSchema())
    blast = services.mark_blast_complete(blast, **data)
    return jsonify(blasting_schema.dump(blast))


# --- Haulage (PQ-09) ------------------------------------------------------------------

@bp.post("/haulage-records")
@require_permission("pq:write")
def create_haulage_record():
    data = _load(HaulageRecordInputSchema())
    record = HaulageRecord(tenant_id=g.tenant_id, **data)
    db.session.add(record)
    db.session.commit()
    return jsonify(haulage_schema.dump(record)), 201


# --- Production reports (PQ-10, PQ-11) --------------------------------------------------

@bp.post("/production-reports")
@require_permission("pq:write")
def create_production_report():
    data = _load(ProductionReportInputSchema())
    report = services.generate_production_report(g.tenant_id, **data)
    return jsonify(report_schema.dump(report)), 201
