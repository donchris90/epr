"""
Module 27 — Subcontractor Portal (Code: SCP)
Request/response schemas.
"""
from marshmallow import Schema, fields, validate

from app.modules.sub.models import CLAIM_TYPES


class SubcontractorPortalUserInputSchema(Schema):
    subcontractor_id = fields.UUID(required=True)
    email = fields.Str(required=True)


class SubcontractorPortalUserSchema(Schema):
    id = fields.UUID(dump_only=True)
    subcontractor_id = fields.UUID(dump_only=True)
    email = fields.Str(dump_only=True)
    is_active = fields.Bool(dump_only=True)


class SubmitProgressSchema(Schema):
    agreement_id = fields.UUID(required=True)
    scope_item_id = fields.UUID(allow_none=True, load_default=None)
    submitted_quantity = fields.Decimal(required=True, as_string=True)


class ProgressEntrySchema(Schema):
    id = fields.UUID(dump_only=True)
    agreement_id = fields.UUID(dump_only=True)
    scope_item_id = fields.UUID(dump_only=True)
    submitted_quantity = fields.Decimal(dump_only=True, as_string=True)
    submitted_at = fields.DateTime(dump_only=True)
    status = fields.Str(dump_only=True)


class PaymentCertificateSchema(Schema):
    id = fields.UUID(dump_only=True)
    agreement_id = fields.UUID(dump_only=True)
    certificate_number = fields.Str(dump_only=True)
    period_start = fields.Date(dump_only=True)
    period_end = fields.Date(dump_only=True)
    gross_certified_amount = fields.Decimal(dump_only=True, as_string=True)
    retention_withheld = fields.Decimal(dump_only=True, as_string=True)
    back_charges_total = fields.Decimal(dump_only=True, as_string=True)
    net_payable = fields.Decimal(dump_only=True, as_string=True)
    status = fields.Str(dump_only=True)
    issued_at = fields.DateTime(dump_only=True)


class SubmitClaimSchema(Schema):
    agreement_id = fields.UUID(required=True)
    claim_type = fields.Str(required=True, validate=validate.OneOf(CLAIM_TYPES))
    description = fields.Str(required=True)
    claimed_amount = fields.Decimal(allow_none=True, as_string=True)
    claimed_days = fields.Int(allow_none=True)


class ClaimSchema(Schema):
    id = fields.UUID(dump_only=True)
    agreement_id = fields.UUID(dump_only=True)
    claim_type = fields.Str(dump_only=True)
    description = fields.Str(dump_only=True)
    claimed_amount = fields.Decimal(dump_only=True, as_string=True)
    claimed_days = fields.Int(dump_only=True)
    status = fields.Str(dump_only=True)
    submitted_at = fields.DateTime(dump_only=True)
    response_notes = fields.Str(dump_only=True)
