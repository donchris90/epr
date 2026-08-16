"""
Module 18 — Client Billing (Code: BIL)
Request/response schemas.
"""
from marshmallow import Schema, fields, validate

from app.modules.bil.models import CLIENT_APPROVAL_METHODS, CLAIM_TYPES, REVENUE_METHODS


class ProgressCertificateInputSchema(Schema):
    contract_id = fields.UUID(allow_none=True)
    project_id = fields.UUID(allow_none=True)
    certificate_number = fields.Str(required=True)
    period_start = fields.Date(allow_none=True)
    period_end = fields.Date(allow_none=True)


class ProgressCertificateSchema(Schema):
    id = fields.UUID(dump_only=True)
    contract_id = fields.UUID(dump_only=True)
    certificate_number = fields.Str(dump_only=True)
    gross_certified_amount = fields.Decimal(dump_only=True, as_string=True)
    retention_withheld = fields.Decimal(dump_only=True, as_string=True)
    net_payable = fields.Decimal(dump_only=True, as_string=True)
    status = fields.Str(dump_only=True)


class AddCertificateLineSchema(Schema):
    boq_item_id = fields.UUID(required=True)
    certified_quantity = fields.Decimal(required=True, as_string=True)
    rate = fields.Decimal(required=True, as_string=True)
    contracted_quantity = fields.Decimal(required=True, as_string=True)
    variation_order_id = fields.UUID(allow_none=True, load_default=None)


class CertificateLineSchema(Schema):
    id = fields.UUID(dump_only=True)
    boq_item_id = fields.UUID(dump_only=True)
    variation_order_id = fields.UUID(dump_only=True)
    certified_quantity = fields.Decimal(dump_only=True, as_string=True)
    amount = fields.Decimal(dump_only=True, as_string=True)


class ApplyRetentionSchema(Schema):
    percentage = fields.Decimal(required=True, as_string=True)


class ApproveCertificateSchema(Schema):
    approval_method = fields.Str(required=True, validate=validate.OneOf(CLIENT_APPROVAL_METHODS))
    approved_by = fields.Str(allow_none=True)


class VariationOrderInputSchema(Schema):
    contract_id = fields.UUID(required=True)
    boq_item_id = fields.UUID(allow_none=True)
    description = fields.Str(required=True)
    varied_quantity = fields.Decimal(allow_none=True, as_string=True)
    varied_rate = fields.Decimal(allow_none=True, as_string=True)


class VariationOrderDecisionSchema(Schema):
    decision = fields.Str(required=True, validate=validate.OneOf(("approved", "rejected")))
    approved_by = fields.Str(allow_none=True)


class VariationOrderSchema(Schema):
    id = fields.UUID(dump_only=True)
    contract_id = fields.UUID(dump_only=True)
    boq_item_id = fields.UUID(dump_only=True)
    varied_quantity = fields.Decimal(dump_only=True, as_string=True)
    status = fields.Str(dump_only=True)


class ClaimInputSchema(Schema):
    contract_id = fields.UUID(required=True)
    claim_type = fields.Str(required=True, validate=validate.OneOf(CLAIM_TYPES))
    description = fields.Str(required=True)
    claimed_amount = fields.Decimal(allow_none=True, as_string=True)
    supporting_document_ids = fields.List(fields.UUID(), allow_none=True)


class ClaimSchema(Schema):
    id = fields.UUID(dump_only=True)
    contract_id = fields.UUID(dump_only=True)
    claim_type = fields.Str(dump_only=True)
    claimed_amount = fields.Decimal(dump_only=True, as_string=True)
    status = fields.Str(dump_only=True)


class RecordPaymentSchema(Schema):
    paid_amount = fields.Decimal(required=True, as_string=True)


class PaymentTrackingSchema(Schema):
    id = fields.UUID(dump_only=True)
    certificate_id = fields.UUID(dump_only=True)
    status = fields.Str(dump_only=True)
    due_date = fields.Date(dump_only=True)
    paid_amount = fields.Decimal(dump_only=True, as_string=True)


class RecognizeRevenueSchema(Schema):
    contract_id = fields.UUID(required=True)
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)
    contract_total_value = fields.Decimal(required=True, as_string=True)
    percentage_complete = fields.Decimal(allow_none=True, as_string=True)
    method = fields.Str(load_default="percentage_of_completion", validate=validate.OneOf(REVENUE_METHODS))


class RevenueRecognitionSchema(Schema):
    id = fields.UUID(dump_only=True)
    contract_id = fields.UUID(dump_only=True)
    method = fields.Str(dump_only=True)
    percentage_complete = fields.Decimal(dump_only=True, as_string=True)
    cumulative_revenue_recognized = fields.Decimal(dump_only=True, as_string=True)
    cumulative_billed = fields.Decimal(dump_only=True, as_string=True)
    over_under_billing_position = fields.Decimal(dump_only=True, as_string=True)
