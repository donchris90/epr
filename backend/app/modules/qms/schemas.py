"""
Module 13 — Quality Management (QMS) (Code: QMS)
Request/response schemas.
"""
from marshmallow import Schema, fields, validate

from app.modules.qms.models import LAB_TEST_TYPES, NCR_DISPOSITIONS, CORRECTIVE_ACTION_SOURCES


class InspectionTestPlanSchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(allow_none=True)
    activity_type = fields.Str(required=True)
    title = fields.Str(required=True)
    description = fields.Str(allow_none=True)
    status = fields.Str(dump_only=True)


class ITPHoldPointInputSchema(Schema):
    sequence_order = fields.Int(required=True)
    description = fields.Str(required=True)
    required_check = fields.Str(allow_none=True)
    acceptance_criteria = fields.Str(allow_none=True)
    is_mandatory_hold = fields.Bool(load_default=True)


class ITPHoldPointSchema(Schema):
    id = fields.UUID(dump_only=True)
    itp_id = fields.UUID(dump_only=True)
    sequence_order = fields.Int(dump_only=True)
    description = fields.Str(dump_only=True)
    is_mandatory_hold = fields.Bool(dump_only=True)
    status = fields.Str(dump_only=True)
    concession_reason = fields.Str(dump_only=True)


class RecordHoldPointResultSchema(Schema):
    passed = fields.Bool(required=True)
    inspection_log_id = fields.UUID(allow_none=True, load_default=None)


class ApproveConcessionSchema(Schema):
    reason = fields.Str(required=True)


class MaterialApprovalInputSchema(Schema):
    material_item_id = fields.UUID(allow_none=True, load_default=None)
    submittal_reference = fields.Str(required=True)
    technical_data_document_id = fields.UUID(allow_none=True)
    submitted_at = fields.DateTime(allow_none=True)


class MaterialApprovalDecisionSchema(Schema):
    decision = fields.Str(required=True, validate=validate.OneOf(("approved", "rejected")))
    reviewed_by = fields.Str(allow_none=True)
    review_notes = fields.Str(allow_none=True)


class MaterialApprovalSchema(Schema):
    id = fields.UUID(dump_only=True)
    material_item_id = fields.UUID(dump_only=True)
    submittal_reference = fields.Str(dump_only=True)
    status = fields.Str(dump_only=True)
    review_notes = fields.Str(dump_only=True)


class LabResultSchema(Schema):
    id = fields.UUID(dump_only=True)
    pour_or_lot_reference = fields.UUID(allow_none=True)
    test_type = fields.Str(required=True, validate=validate.OneOf(LAB_TEST_TYPES))
    sample_reference = fields.Str(allow_none=True)
    tested_at = fields.Date(allow_none=True)
    result_value = fields.Decimal(allow_none=True, as_string=True)
    unit = fields.Str(allow_none=True)
    acceptance_threshold = fields.Decimal(allow_none=True, as_string=True)
    pass_fail = fields.Bool(dump_only=True)
    lab_name = fields.Str(allow_none=True)


class RecordLabResultOutcomeSchema(Schema):
    pass_fail = fields.Bool(required=True)


class NCRInputSchema(Schema):
    project_id = fields.UUID(allow_none=True)
    description = fields.Str(required=True)
    photo_document_ids = fields.List(fields.UUID(), allow_none=True)
    root_cause = fields.Str(allow_none=True)


class NCRDispositionSchema(Schema):
    disposition = fields.Str(required=True, validate=validate.OneOf(NCR_DISPOSITIONS))


class NCRSchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(dump_only=True)
    description = fields.Str(dump_only=True)
    root_cause = fields.Str(dump_only=True)
    disposition = fields.Str(dump_only=True)
    status = fields.Str(dump_only=True)
    closed_at = fields.DateTime(dump_only=True)


class CorrectiveActionInputSchema(Schema):
    ncr_id = fields.UUID(allow_none=True, load_default=None)
    source = fields.Str(load_default="ncr", validate=validate.OneOf(CORRECTIVE_ACTION_SOURCES))
    description = fields.Str(required=True)
    owner_id = fields.UUID(allow_none=True)
    due_date = fields.Date(allow_none=True)


class CorrectiveActionSchema(Schema):
    id = fields.UUID(dump_only=True)
    ncr_id = fields.UUID(dump_only=True)
    source = fields.Str(dump_only=True)
    description = fields.Str(dump_only=True)
    status = fields.Str(dump_only=True)
    verified_by = fields.UUID(dump_only=True)
    verified_at = fields.DateTime(dump_only=True)


class PunchListItemInputSchema(Schema):
    project_id = fields.UUID(required=True)
    area_building_section = fields.Str(allow_none=True)
    description = fields.Str(required=True)


class PunchListItemSchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(dump_only=True)
    area_building_section = fields.Str(dump_only=True)
    description = fields.Str(dump_only=True)
    status = fields.Str(dump_only=True)


class SnagListItemInputSchema(Schema):
    project_id = fields.UUID(required=True)
    area_building_section = fields.Str(allow_none=True)
    description = fields.Str(required=True)


class SnagListItemSchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(dump_only=True)
    area_building_section = fields.Str(dump_only=True)
    description = fields.Str(dump_only=True)
    status = fields.Str(dump_only=True)
