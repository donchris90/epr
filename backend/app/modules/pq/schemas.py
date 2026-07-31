"""
Module 16 — Plant & Quarry Management (Code: PQ)
Request/response schemas.
"""
from marshmallow import Schema, fields, validate

from app.modules.pq.models import EXPLOSIVES_ENTRY_TYPES


class CrusherProductionInputSchema(Schema):
    plant_name = fields.Str(required=True)
    shift_date = fields.Date(required=True)
    shift = fields.Str(allow_none=True)
    input_material = fields.Str(allow_none=True)
    input_quantity = fields.Decimal(allow_none=True, as_string=True)
    output_gradation = fields.Dict(allow_none=True)
    downtime_minutes = fields.Int(load_default=0)
    downtime_reason = fields.Str(allow_none=True)


class CrusherProductionSchema(Schema):
    id = fields.UUID(dump_only=True)
    plant_name = fields.Str(dump_only=True)
    shift_date = fields.Date(dump_only=True)
    downtime_minutes = fields.Int(dump_only=True)


class AsphaltBatchInputSchema(Schema):
    plant_name = fields.Str(required=True)
    mix_design_reference = fields.Str(allow_none=True)
    batch_date = fields.DateTime(allow_none=True)
    temperature = fields.Decimal(allow_none=True, as_string=True)
    quantity_produced = fields.Decimal(allow_none=True, as_string=True)
    unit = fields.Str(allow_none=True)
    lab_result_id = fields.UUID(allow_none=True)


class AsphaltBatchSchema(Schema):
    id = fields.UUID(dump_only=True)
    plant_name = fields.Str(dump_only=True)
    quantity_produced = fields.Decimal(dump_only=True, as_string=True)


class ConcreteBatchInputSchema(Schema):
    plant_name = fields.Str(required=True)
    mix_design_reference = fields.Str(allow_none=True)
    batch_date = fields.DateTime(allow_none=True)
    batch_weights = fields.Dict(allow_none=True)
    water_cement_ratio = fields.Decimal(allow_none=True, as_string=True)
    quantity_produced = fields.Decimal(allow_none=True, as_string=True)
    destination_pour_reference = fields.UUID(allow_none=True)


class ConcreteBatchSchema(Schema):
    id = fields.UUID(dump_only=True)
    plant_name = fields.Str(dump_only=True)
    water_cement_ratio = fields.Decimal(dump_only=True, as_string=True)


class QuarryProductionInputSchema(Schema):
    quarry_name = fields.Str(required=True)
    face_or_bench = fields.Str(allow_none=True)
    material_type = fields.Str(allow_none=True)
    volume_extracted = fields.Decimal(allow_none=True, as_string=True)
    production_date = fields.Date(allow_none=True)


class QuarryProductionSchema(Schema):
    id = fields.UUID(dump_only=True)
    quarry_name = fields.Str(dump_only=True)
    volume_extracted = fields.Decimal(dump_only=True, as_string=True)


class StockpileInputSchema(Schema):
    material_type = fields.Str(required=True)
    location = fields.Str(allow_none=True)
    quantity = fields.Decimal(load_default="0", as_string=True)


class ReconcileStockpileSchema(Schema):
    physical_quantity = fields.Decimal(required=True, as_string=True)
    tolerance = fields.Decimal(load_default="0", as_string=True)


class StockpileSchema(Schema):
    id = fields.UUID(dump_only=True)
    material_type = fields.Str(dump_only=True)
    quantity = fields.Decimal(dump_only=True, as_string=True)
    last_reconciled_at = fields.DateTime(dump_only=True)


class ExplosivesEntryInputSchema(Schema):
    entry_type = fields.Str(required=True, validate=validate.OneOf(EXPLOSIVES_ENTRY_TYPES))
    material_type = fields.Str(required=True)
    quantity = fields.Decimal(required=True, as_string=True)
    unit = fields.Str(allow_none=True)
    entry_date = fields.DateTime(allow_none=True)
    reference_number = fields.Str(allow_none=True)


class ExplosivesEntrySchema(Schema):
    id = fields.UUID(dump_only=True)
    entry_type = fields.Str(dump_only=True)
    material_type = fields.Str(dump_only=True)
    quantity = fields.Decimal(dump_only=True, as_string=True)


class ExplosivesCorrectionInputSchema(Schema):
    reason = fields.Str(required=True)
    corrected_quantity = fields.Decimal(allow_none=True, as_string=True)


class ExplosivesCorrectionSchema(Schema):
    id = fields.UUID(dump_only=True)
    entry_id = fields.UUID(dump_only=True)
    reason = fields.Str(dump_only=True)
    corrected_quantity = fields.Decimal(dump_only=True, as_string=True)


class DrillingRecordInputSchema(Schema):
    quarry_name = fields.Str(required=True)
    pattern_reference = fields.Str(allow_none=True)
    hole_count = fields.Int(allow_none=True)
    depth = fields.Decimal(allow_none=True, as_string=True)
    drilled_at = fields.DateTime(allow_none=True)


class DrillingRecordSchema(Schema):
    id = fields.UUID(dump_only=True)
    quarry_name = fields.Str(dump_only=True)
    hole_count = fields.Int(dump_only=True)


class BlastingRecordInputSchema(Schema):
    drilling_record_id = fields.UUID(required=True)
    explosives_used = fields.List(fields.Dict(), allow_none=True)
    blast_design = fields.Str(allow_none=True)
    vibration_monitoring_result = fields.Decimal(allow_none=True, as_string=True)
    fly_rock_monitoring_result = fields.Str(allow_none=True)
    regulatory_notification_reference = fields.Str(allow_none=True)
    blast_date = fields.DateTime(allow_none=True)


class MarkBlastCompleteSchema(Schema):
    requires_regulatory_notification = fields.Bool(load_default=False)


class BlastingRecordSchema(Schema):
    id = fields.UUID(dump_only=True)
    drilling_record_id = fields.UUID(dump_only=True)
    status = fields.Str(dump_only=True)
    regulatory_notification_reference = fields.Str(dump_only=True)


class HaulageRecordInputSchema(Schema):
    source = fields.Str(allow_none=True)
    destination = fields.Str(allow_none=True)
    load_count = fields.Int(allow_none=True)
    tonnage = fields.Decimal(allow_none=True, as_string=True)
    cycle_time_minutes = fields.Int(allow_none=True)
    haul_date = fields.Date(allow_none=True)


class HaulageRecordSchema(Schema):
    id = fields.UUID(dump_only=True)
    tonnage = fields.Decimal(dump_only=True, as_string=True)


class ProductionReportInputSchema(Schema):
    plant_or_quarry_name = fields.Str(required=True)
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)
    total_output = fields.Decimal(required=True, as_string=True)
    cost_per_unit = fields.Decimal(allow_none=True, as_string=True)
    target_output = fields.Decimal(allow_none=True, as_string=True)


class ProductionReportSchema(Schema):
    id = fields.UUID(dump_only=True)
    plant_or_quarry_name = fields.Str(dump_only=True)
    total_output = fields.Decimal(dump_only=True, as_string=True)
    yield_efficiency_pct = fields.Decimal(dump_only=True, as_string=True)
    cost_per_unit = fields.Decimal(dump_only=True, as_string=True)
