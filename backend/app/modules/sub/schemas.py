"""
Module 12 — Subcontractor Management (Code: SUB)
Request/response schemas.
"""
from marshmallow import Schema, fields, validate

from app.modules.sub.models import (
    BACK_CHARGE_CATEGORIES,
    CLAIM_TYPES,
    COMPLIANCE_DOC_TYPES,
)


class SubcontractorSchema(Schema):
    id = fields.UUID(dump_only=True)
    name = fields.Str(required=True)
    trade_specialty = fields.Str(allow_none=True)
    tax_registration_number = fields.Str(allow_none=True)
    status = fields.Str(dump_only=True)


class SubcontractAgreementSchema(Schema):
    id = fields.UUID(dump_only=True)
    subcontractor_id = fields.UUID(required=True)
    contract_id = fields.UUID(allow_none=True)
    agreement_number = fields.Str(required=True)
    value = fields.Decimal(required=True, as_string=True)
    currency = fields.Str(load_default="NGN")
    payment_terms_summary = fields.Str(allow_none=True)
    retention_percentage = fields.Decimal(load_default="5", as_string=True)
    status = fields.Str(dump_only=True)


class SubcontractScopeItemSchema(Schema):
    id = fields.UUID(dump_only=True)
    agreement_id = fields.UUID(dump_only=True)
    boq_item_id = fields.UUID(allow_none=True)
    cbs_line_item_id = fields.UUID(allow_none=True)
    description = fields.Str(required=True)
    is_lump_sum = fields.Bool(load_default=False)
    quantity = fields.Decimal(allow_none=True, as_string=True)
    unit = fields.Str(allow_none=True)
    rate = fields.Decimal(allow_none=True, as_string=True)
    lump_sum_amount = fields.Decimal(allow_none=True, as_string=True)


class SubcontractProgressEntrySchema(Schema):
    id = fields.UUID(dump_only=True)
    agreement_id = fields.UUID(dump_only=True)
    scope_item_id = fields.UUID(allow_none=True)
    submitted_quantity = fields.Decimal(required=True, as_string=True)
    submitted_at = fields.DateTime(allow_none=True)
    status = fields.Str(dump_only=True)


class MeasurementSheetInputSchema(Schema):
    agreement_id = fields.UUID(required=True)
    scope_item_id = fields.UUID(required=True)
    progress_entry_id = fields.UUID(allow_none=True, load_default=None)
    verified_quantity = fields.Decimal(required=True, as_string=True)


class MeasurementSheetSchema(Schema):
    id = fields.UUID(dump_only=True)
    agreement_id = fields.UUID(dump_only=True)
    scope_item_id = fields.UUID(dump_only=True)
    verified_quantity = fields.Decimal(dump_only=True, as_string=True)
    status = fields.Str(dump_only=True)
    measured_by = fields.UUID(dump_only=True)
    measured_at = fields.DateTime(dump_only=True)


class IssuePaymentCertificateSchema(Schema):
    certificate_number = fields.Str(required=True)
    measurement_sheet_ids = fields.List(fields.UUID(), required=True)
    period_start = fields.Date(allow_none=True)
    period_end = fields.Date(allow_none=True)
    back_charge_ids = fields.List(fields.UUID(), load_default=list)
    waiver = fields.Bool(load_default=False)
    waiver_reason = fields.Str(allow_none=True)


class PaymentCertificateLineSchema(Schema):
    id = fields.UUID(dump_only=True)
    measurement_sheet_id = fields.UUID(dump_only=True)
    certified_quantity = fields.Decimal(dump_only=True, as_string=True)
    rate = fields.Decimal(dump_only=True, as_string=True)
    amount = fields.Decimal(dump_only=True, as_string=True)


class PaymentCertificateSchema(Schema):
    id = fields.UUID(dump_only=True)
    agreement_id = fields.UUID(dump_only=True)
    certificate_number = fields.Str(dump_only=True)
    gross_certified_amount = fields.Decimal(dump_only=True, as_string=True)
    retention_withheld = fields.Decimal(dump_only=True, as_string=True)
    back_charges_total = fields.Decimal(dump_only=True, as_string=True)
    net_payable = fields.Decimal(dump_only=True, as_string=True)
    status = fields.Str(dump_only=True)
    compliance_waiver = fields.Bool(dump_only=True)
    lines = fields.List(fields.Nested(PaymentCertificateLineSchema), dump_only=True)


class BackChargeInputSchema(Schema):
    description = fields.Str(required=True)
    amount = fields.Decimal(required=True, as_string=True)
    reason_category = fields.Str(load_default="other", validate=validate.OneOf(BACK_CHARGE_CATEGORIES))


class BackChargeSchema(Schema):
    id = fields.UUID(dump_only=True)
    agreement_id = fields.UUID(dump_only=True)
    payment_certificate_id = fields.UUID(dump_only=True)
    description = fields.Str(dump_only=True)
    amount = fields.Decimal(dump_only=True, as_string=True)
    reason_category = fields.Str(dump_only=True)


class SubcontractRetentionSchema(Schema):
    id = fields.UUID(dump_only=True)
    agreement_id = fields.UUID(dump_only=True)
    percentage = fields.Decimal(dump_only=True, as_string=True)
    amount_withheld = fields.Decimal(dump_only=True, as_string=True)
    released_substantial_completion = fields.Bool(dump_only=True)
    released_final = fields.Bool(dump_only=True)


class ReleaseRetentionSchema(Schema):
    stage = fields.Str(required=True, validate=validate.OneOf(("substantial_completion", "final")))


class SubcontractClaimInputSchema(Schema):
    claim_type = fields.Str(required=True, validate=validate.OneOf(CLAIM_TYPES))
    description = fields.Str(required=True)
    claimed_amount = fields.Decimal(allow_none=True, as_string=True)
    claimed_days = fields.Int(allow_none=True)


class SubcontractClaimSchema(Schema):
    id = fields.UUID(dump_only=True)
    agreement_id = fields.UUID(dump_only=True)
    claim_type = fields.Str(dump_only=True)
    description = fields.Str(dump_only=True)
    claimed_amount = fields.Decimal(dump_only=True, as_string=True)
    status = fields.Str(dump_only=True)
    response_notes = fields.Str(dump_only=True)


class ClaimReviewSchema(Schema):
    decision = fields.Str(required=True, validate=validate.OneOf(("approved", "rejected", "under_review")))
    response_notes = fields.Str(allow_none=True)


class PerformanceRatingInputSchema(Schema):
    project_id = fields.UUID(allow_none=True, load_default=None)
    period_label = fields.Str(allow_none=True)
    quality_score = fields.Decimal(required=True, as_string=True)
    schedule_score = fields.Decimal(required=True, as_string=True)
    safety_score = fields.Decimal(required=True, as_string=True)
    responsiveness_score = fields.Decimal(required=True, as_string=True)


class PerformanceRatingSchema(Schema):
    id = fields.UUID(dump_only=True)
    subcontractor_id = fields.UUID(dump_only=True)
    project_id = fields.UUID(dump_only=True)
    overall_score = fields.Decimal(dump_only=True, as_string=True)


class ComplianceDocumentInputSchema(Schema):
    doc_type = fields.Str(required=True, validate=validate.OneOf(COMPLIANCE_DOC_TYPES))
    document_id = fields.UUID(allow_none=True)
    valid_until = fields.Date(allow_none=True)


class ComplianceDocumentSchema(Schema):
    id = fields.UUID(dump_only=True)
    subcontractor_id = fields.UUID(dump_only=True)
    doc_type = fields.Str(dump_only=True)
    valid_until = fields.Date(dump_only=True)
