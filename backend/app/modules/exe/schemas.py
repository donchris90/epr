"""
Module 6 — Project Execution (Code: EXE)
Request/response schemas.
"""
from marshmallow import Schema, fields, validate

from app.modules.exe.models import (
    MEDIA_TYPES,
    PROGRESS_MEASUREMENT_TYPES,
    ISSUE_SEVERITIES,
    ISSUE_STATUSES,
    INSPECTION_OUTCOMES,
)


class DailySiteDiarySchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(required=True)
    diary_date = fields.Date(required=True)
    workforce_present_count = fields.Int(allow_none=True)
    equipment_on_site_summary = fields.Str(allow_none=True)
    narrative = fields.Str(allow_none=True)
    status = fields.Str(dump_only=True)
    signed_by = fields.UUID(dump_only=True)
    signed_at = fields.DateTime(dump_only=True)
    countersigned_by = fields.UUID(dump_only=True)
    countersigned_at = fields.DateTime(dump_only=True)


class UpdateDiarySchema(Schema):
    workforce_present_count = fields.Int(allow_none=True)
    equipment_on_site_summary = fields.Str(allow_none=True)
    narrative = fields.Str(allow_none=True)


class DiaryAmendmentSchema(Schema):
    id = fields.UUID(dump_only=True)
    diary_id = fields.UUID(dump_only=True)
    description = fields.Str(required=True)
    amended_by = fields.UUID(dump_only=True)
    created_at = fields.DateTime(dump_only=True)


class SiteMediaSchema(Schema):
    id = fields.UUID(dump_only=True)
    document_id = fields.UUID(required=True)
    media_type = fields.Str(required=True, validate=validate.OneOf(MEDIA_TYPES))
    diary_id = fields.UUID(allow_none=True)
    activity_id = fields.UUID(allow_none=True)
    inspection_log_id = fields.UUID(allow_none=True)
    latitude = fields.Decimal(allow_none=True, as_string=True)
    longitude = fields.Decimal(allow_none=True, as_string=True)
    captured_at = fields.DateTime(allow_none=True)


class WeatherRecordSchema(Schema):
    id = fields.UUID(dump_only=True)
    diary_id = fields.UUID(dump_only=True)
    recorded_at = fields.DateTime(allow_none=True)
    condition = fields.Str(allow_none=True)
    temperature_c = fields.Decimal(allow_none=True, as_string=True)
    rainfall_mm = fields.Decimal(allow_none=True, as_string=True)
    wind_kph = fields.Decimal(allow_none=True, as_string=True)
    source = fields.Str(load_default="manual")


class ProgressEntrySchema(Schema):
    id = fields.UUID(dump_only=True)
    diary_id = fields.UUID(allow_none=True, load_default=None)
    activity_id = fields.UUID(required=True)
    measurement_type = fields.Str(required=True, validate=validate.OneOf(PROGRESS_MEASUREMENT_TYPES))
    value = fields.Decimal(required=True, as_string=True)
    unit = fields.Str(allow_none=True)
    recorded_at = fields.DateTime(allow_none=True)


class WorkCompletedRecordSchema(Schema):
    id = fields.UUID(dump_only=True)
    diary_id = fields.UUID(allow_none=True)
    boq_item_id = fields.UUID(required=True)
    quantity = fields.Decimal(required=True, as_string=True)
    contracted_quantity = fields.Decimal(required=True, as_string=True, load_only=True)
    unit = fields.Str(allow_none=True)
    recorded_at = fields.DateTime(allow_none=True)
    variation_order_id = fields.UUID(allow_none=True, load_default=None)
    exceeds_contracted_quantity = fields.Bool(dump_only=True)


class SiteIssueSchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(required=True)
    diary_id = fields.UUID(allow_none=True, load_default=None)
    category = fields.Str(allow_none=True)
    severity = fields.Str(load_default="medium", validate=validate.OneOf(ISSUE_SEVERITIES))
    description = fields.Str(required=True)
    assigned_owner_id = fields.UUID(allow_none=True)
    status = fields.Str(validate=validate.OneOf(ISSUE_STATUSES), dump_only=True)
    due_date = fields.Date(allow_none=True)
    resolved_at = fields.DateTime(dump_only=True)
    escalated_at = fields.DateTime(dump_only=True)


class VisitorLogSchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(required=True)
    diary_id = fields.UUID(allow_none=True, load_default=None)
    visitor_name = fields.Str(required=True)
    company = fields.Str(allow_none=True)
    purpose = fields.Str(allow_none=True)
    hse_induction_verified = fields.Bool(load_default=False)
    signed_in_at = fields.DateTime(allow_none=True)
    signed_out_at = fields.DateTime(allow_none=True)


class EquipmentUsageRecordSchema(Schema):
    id = fields.UUID(dump_only=True)
    diary_id = fields.UUID(dump_only=True)
    activity_id = fields.UUID(allow_none=True)
    equipment_identifier = fields.Str(required=True)
    hours_used = fields.Decimal(required=True, as_string=True)
    fuel_used_litres = fields.Decimal(allow_none=True, as_string=True)
    operator_name = fields.Str(allow_none=True)


class LaborUsageRecordSchema(Schema):
    id = fields.UUID(dump_only=True)
    diary_id = fields.UUID(dump_only=True)
    activity_id = fields.UUID(allow_none=True)
    trade = fields.Str(required=True)
    headcount = fields.Int(required=True)
    hours_worked = fields.Decimal(required=True, as_string=True)


class ConcretePourRecordSchema(Schema):
    id = fields.UUID(dump_only=True)
    diary_id = fields.UUID(allow_none=True, load_default=None)
    activity_id = fields.UUID(allow_none=True)
    inspection_log_id = fields.UUID(allow_none=True)
    mix_design = fields.Str(allow_none=True)
    volume_m3 = fields.Decimal(required=True, as_string=True)
    slump_mm = fields.Decimal(allow_none=True, as_string=True)
    cube_references = fields.List(fields.Str(), allow_none=True)
    weather_at_pour = fields.Str(allow_none=True)
    pour_started_at = fields.DateTime(allow_none=True)
    pour_completed_at = fields.DateTime(allow_none=True)


class InspectionLogSchema(Schema):
    id = fields.UUID(dump_only=True)
    diary_id = fields.UUID(allow_none=True, load_default=None)
    itp_reference = fields.Str(allow_none=True)
    inspected_item = fields.Str(required=True)
    outcome = fields.Str(required=True, validate=validate.OneOf(INSPECTION_OUTCOMES))
    inspector_name = fields.Str(allow_none=True)
    inspected_at = fields.DateTime(allow_none=True)
    notes = fields.Str(allow_none=True)
