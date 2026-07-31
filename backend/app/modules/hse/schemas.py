"""
Module 14 — Health, Safety & Environment (HSE) (Code: HSE)
Request/response schemas.
"""
from marshmallow import Schema, fields, validate

from app.modules.hse.models import (
    PERMIT_TYPES,
    INCIDENT_CLASSIFICATIONS,
    SAFETY_AUDIT_TYPES,
    ENV_MONITORING_TYPES,
    WASTE_TYPES,
)


class RiskAssessmentSchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(allow_none=True)
    activity_or_area = fields.Str(required=True)
    description = fields.Str(allow_none=True)
    risk_level = fields.Str(allow_none=True)
    status = fields.Str(dump_only=True)
    valid_until = fields.Date(allow_none=True)
    review_interval_days = fields.Int(allow_none=True)


class IssuePermitSchema(Schema):
    project_id = fields.UUID(required=True)
    permit_type = fields.Str(required=True, validate=validate.OneOf(PERMIT_TYPES))
    risk_assessment_id = fields.UUID(allow_none=True, load_default=None)
    description = fields.Str(allow_none=True)
    workers_training_current = fields.Bool(load_default=True)


class ActivatePermitSchema(Schema):
    valid_until = fields.DateTime(allow_none=True)


class PermitToWorkSchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(dump_only=True)
    permit_type = fields.Str(dump_only=True)
    status = fields.Str(dump_only=True)
    formally_closed = fields.Bool(dump_only=True)
    closed_at = fields.DateTime(dump_only=True)
    valid_until = fields.DateTime(dump_only=True)


class IncidentInputSchema(Schema):
    project_id = fields.UUID(allow_none=True, load_default=None)
    classification = fields.Str(required=True, validate=validate.OneOf(INCIDENT_CLASSIFICATIONS))
    description = fields.Str(required=True)
    regulatory_reportable = fields.Bool(load_default=False)
    occurred_at = fields.DateTime(allow_none=True)


class IncidentSchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(dump_only=True)
    classification = fields.Str(dump_only=True)
    description = fields.Str(dump_only=True)
    status = fields.Str(dump_only=True)
    corrective_action_id = fields.UUID(dump_only=True)


class NearMissInputSchema(Schema):
    project_id = fields.UUID(allow_none=True, load_default=None)
    classification = fields.Str(required=True, validate=validate.OneOf(INCIDENT_CLASSIFICATIONS))
    description = fields.Str(required=True)
    occurred_at = fields.DateTime(allow_none=True)


class NearMissSchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(dump_only=True)
    classification = fields.Str(dump_only=True)
    description = fields.Str(dump_only=True)


class ToolboxTalkInputSchema(Schema):
    project_id = fields.UUID(allow_none=True)
    topic = fields.Str(required=True)
    facilitator_id = fields.UUID(allow_none=True)
    held_at = fields.DateTime(allow_none=True)


class ToolboxTalkAttendeeInputSchema(Schema):
    employee_id = fields.UUID(allow_none=True, load_default=None)
    casual_worker_id = fields.UUID(allow_none=True, load_default=None)


class ToolboxTalkSchema(Schema):
    id = fields.UUID(dump_only=True)
    topic = fields.Str(dump_only=True)
    facilitator_signed = fields.Bool(dump_only=True)


class PPERecordInputSchema(Schema):
    employee_id = fields.UUID(allow_none=True, load_default=None)
    casual_worker_id = fields.UUID(allow_none=True, load_default=None)
    material_item_id = fields.UUID(allow_none=True)
    ppe_type = fields.Str(required=True)
    quantity = fields.Int(load_default=1)
    issued_at = fields.DateTime(allow_none=True)


class PPERecordSchema(Schema):
    id = fields.UUID(dump_only=True)
    ppe_type = fields.Str(dump_only=True)
    quantity = fields.Int(dump_only=True)


class SafetyAuditInputSchema(Schema):
    project_id = fields.UUID(allow_none=True)
    audit_type = fields.Str(load_default="scheduled", validate=validate.OneOf(SAFETY_AUDIT_TYPES))
    checklist = fields.List(fields.Dict(), allow_none=True)
    score = fields.Decimal(allow_none=True, as_string=True)
    audit_date = fields.Date(allow_none=True)


class SafetyAuditSchema(Schema):
    id = fields.UUID(dump_only=True)
    audit_type = fields.Str(dump_only=True)
    score = fields.Decimal(dump_only=True, as_string=True)


class EnvironmentalMonitoringInputSchema(Schema):
    project_id = fields.UUID(allow_none=True)
    monitoring_type = fields.Str(required=True, validate=validate.OneOf(ENV_MONITORING_TYPES))
    recorded_at = fields.DateTime(allow_none=True)
    value = fields.Decimal(allow_none=True, as_string=True)
    unit = fields.Str(allow_none=True)
    threshold = fields.Decimal(allow_none=True, as_string=True)


class EnvironmentalMonitoringSchema(Schema):
    id = fields.UUID(dump_only=True)
    monitoring_type = fields.Str(dump_only=True)
    value = fields.Decimal(dump_only=True, as_string=True)
    exceeds_threshold = fields.Bool(dump_only=True)


class WasteDisposalInputSchema(Schema):
    project_id = fields.UUID(allow_none=True)
    waste_type = fields.Str(required=True, validate=validate.OneOf(WASTE_TYPES))
    quantity = fields.Decimal(allow_none=True, as_string=True)
    unit = fields.Str(allow_none=True)
    disposed_at = fields.Date(allow_none=True)
    manifest_document_id = fields.UUID(allow_none=True)
    disposal_certificate_document_id = fields.UUID(allow_none=True)


class WasteDisposalSchema(Schema):
    id = fields.UUID(dump_only=True)
    waste_type = fields.Str(dump_only=True)
    quantity = fields.Decimal(dump_only=True, as_string=True)


class EmergencyResponsePlanInputSchema(Schema):
    project_id = fields.UUID(required=True)
    muster_points = fields.List(fields.Dict(), allow_none=True)
    emergency_contacts = fields.List(fields.Dict(), allow_none=True)
    designated_roles = fields.List(fields.Dict(), allow_none=True)
    effective_from = fields.Date(allow_none=True)


class EmergencyResponsePlanSchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(dump_only=True)
    version = fields.Int(dump_only=True)
    muster_points = fields.List(fields.Dict(), dump_only=True)
    emergency_contacts = fields.List(fields.Dict(), dump_only=True)


class SafetyIndicatorsQuerySchema(Schema):
    project_id = fields.UUID(allow_none=True, load_default=None)
    period_start = fields.DateTime(required=True)
    period_end = fields.DateTime(required=True)
    total_hours_worked = fields.Decimal(required=True, as_string=True)
