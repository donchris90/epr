"""
Module 4 — Contract Management (Code: CTM)
Request/response schemas.
"""
from marshmallow import Schema, fields, validate

from app.modules.ctm.models import CONTRACT_STATUSES, INSTRUMENT_STATUSES, AMENDMENT_TYPES


class ContractSchema(Schema):
    id = fields.UUID(dump_only=True)
    tender_id = fields.UUID(required=True)
    cbs_id = fields.UUID(allow_none=True)
    project_id = fields.UUID(allow_none=True)
    contract_number = fields.Str(required=True)
    contract_value = fields.Decimal(required=True, as_string=True)
    currency = fields.Str(load_default="NGN")
    base_currency = fields.Str(load_default="NGN")
    payment_cycle_days = fields.Int(allow_none=True)
    certification_frequency = fields.Str(allow_none=True)
    status = fields.Str(validate=validate.OneOf(CONTRACT_STATUSES), dump_only=True)
    start_date = fields.Date(allow_none=True)
    completion_date = fields.Date(allow_none=True)
    original_completion_date = fields.Date(dump_only=True)
    created_at = fields.DateTime(dump_only=True)


class ContractDocumentSchema(Schema):
    id = fields.UUID(dump_only=True)
    contract_id = fields.UUID(dump_only=True)
    document_id = fields.UUID(allow_none=True)
    doc_type = fields.Str(required=True)


class PaymentTermSchema(Schema):
    id = fields.UUID(dump_only=True)
    contract_id = fields.UUID(dump_only=True)
    description = fields.Str(required=True)
    trigger = fields.Str(allow_none=True)
    amount = fields.Decimal(allow_none=True, as_string=True)
    percentage_of_contract_value = fields.Decimal(allow_none=True, as_string=True)


class PerformanceBondSchema(Schema):
    id = fields.UUID(dump_only=True)
    contract_id = fields.UUID(dump_only=True)
    amount = fields.Decimal(required=True, as_string=True)
    issuing_bank = fields.Str(allow_none=True)
    valid_from = fields.Date(allow_none=True)
    valid_until = fields.Date(allow_none=True)
    status = fields.Str(validate=validate.OneOf(INSTRUMENT_STATUSES), dump_default="active")


class AdvancePaymentSchema(Schema):
    id = fields.UUID(dump_only=True)
    contract_id = fields.UUID(dump_only=True)
    percentage_of_contract_value = fields.Decimal(required=True, as_string=True)
    amount = fields.Decimal(required=True, as_string=True)
    recoupment_pct_per_certificate = fields.Decimal(required=True, as_string=True)
    amount_recouped = fields.Decimal(dump_only=True, as_string=True)
    paid_at = fields.Date(allow_none=True)


class ApplyCertificateSchema(Schema):
    certificate_amount = fields.Decimal(required=True, as_string=True)


class RetentionSchema(Schema):
    id = fields.UUID(dump_only=True)
    contract_id = fields.UUID(dump_only=True)
    percentage = fields.Decimal(required=True, as_string=True)
    cap_amount = fields.Decimal(allow_none=True, as_string=True)
    amount_withheld = fields.Decimal(dump_only=True, as_string=True)
    release_substantial_completion_pct = fields.Decimal(load_default="50", as_string=True)
    release_end_of_dlp_pct = fields.Decimal(load_default="50", as_string=True)
    released_substantial_completion = fields.Bool(dump_only=True)
    released_end_of_dlp = fields.Bool(dump_only=True)


class ReleaseRetentionSchema(Schema):
    stage = fields.Str(required=True, validate=validate.OneOf(("substantial_completion", "end_of_dlp")))


class InsuranceSchema(Schema):
    id = fields.UUID(dump_only=True)
    contract_id = fields.UUID(dump_only=True)
    policy_type = fields.Str(required=True)
    insurer = fields.Str(allow_none=True)
    coverage_amount = fields.Decimal(allow_none=True, as_string=True)
    valid_from = fields.Date(allow_none=True)
    valid_until = fields.Date(allow_none=True)
    status = fields.Str(validate=validate.OneOf(INSTRUMENT_STATUSES), dump_default="active")


class GuaranteeSchema(Schema):
    id = fields.UUID(dump_only=True)
    contract_id = fields.UUID(dump_only=True)
    guarantee_type = fields.Str(required=True)
    amount = fields.Decimal(required=True, as_string=True)
    issuing_bank = fields.Str(allow_none=True)
    valid_from = fields.Date(allow_none=True)
    valid_until = fields.Date(allow_none=True)
    status = fields.Str(validate=validate.OneOf(INSTRUMENT_STATUSES), dump_default="active")


class ContractAmendmentSchema(Schema):
    id = fields.UUID(dump_only=True)
    contract_id = fields.UUID(dump_only=True)
    amendment_type = fields.Str(required=True, validate=validate.OneOf(AMENDMENT_TYPES))
    description = fields.Str(required=True)
    time_extension_days = fields.Int(allow_none=True)
    price_delta = fields.Decimal(allow_none=True, as_string=True)
    scope_change_description = fields.Str(allow_none=True)
    approved_at = fields.DateTime(dump_only=True)
