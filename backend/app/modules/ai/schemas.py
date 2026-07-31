"""
Module 25 — AI Construction Assistant (Code: AI)
Request/response schemas.
"""
from marshmallow import Schema, fields, validate

from app.modules.ai.models import EXTRACTION_TYPES, REPORT_TYPES


class AtRiskProjectsQuerySchema(Schema):
    threshold = fields.Decimal(load_default="0.9", as_string=True)


class IdleEquipmentQuerySchema(Schema):
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)


class ExplainDelayQuerySchema(Schema):
    project_id = fields.UUID(required=True)


class GenerateReportSchema(Schema):
    report_type = fields.Str(required=True, validate=validate.OneOf(REPORT_TYPES))
    content = fields.Dict(required=True)
    source_citations = fields.Dict(required=True)


class ReportSchema(Schema):
    id = fields.UUID(dump_only=True)
    report_type = fields.Str(dump_only=True)
    content = fields.Dict(dump_only=True)
    source_citations = fields.Dict(dump_only=True)
    generated_at = fields.DateTime(dump_only=True)


class CreateExtractionJobSchema(Schema):
    source_document_id = fields.UUID(allow_none=True, load_default=None)
    extraction_type = fields.Str(required=True, validate=validate.OneOf(EXTRACTION_TYPES))
    extracted_data = fields.Dict(required=True)
    confidence_scores = fields.Dict(allow_none=True, load_default=dict)


class ReviewExtractionSchema(Schema):
    corrected_data = fields.Dict(allow_none=True, load_default=None)


class CommitBOQExtractionSchema(Schema):
    estimate_version_id = fields.UUID(required=True)


class ExtractionJobSchema(Schema):
    id = fields.UUID(dump_only=True)
    extraction_type = fields.Str(dump_only=True)
    status = fields.Str(dump_only=True)
    extracted_data = fields.Dict(dump_only=True)
    low_confidence_fields = fields.List(fields.Str(), dump_only=True)
    committed_record_id = fields.UUID(dump_only=True, allow_none=True)
