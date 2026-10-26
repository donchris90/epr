"""
Module 23 — Vendor Portal (Code: VNP)
Request/response schemas.
"""
from marshmallow import Schema, fields, validate


class VendorPortalUserInputSchema(Schema):
    vendor_id = fields.UUID(required=True)
    email = fields.Str(required=True)
    # load_only + not a model column -- popped off in the route and
    # passed to services.set_vendor_password separately, since the
    # model stores password_hash, never the plaintext value.
    password = fields.Str(required=True, load_only=True, validate=validate.Length(min=8))


class VendorLoginSchema(Schema):
    email = fields.Str(required=True)
    password = fields.Str(required=True)


class ChangeVendorPasswordSchema(Schema):
    current_password = fields.Str(required=True)
    new_password = fields.Str(required=True, validate=validate.Length(min=8))


class VendorPortalUserSchema(Schema):
    id = fields.UUID(dump_only=True)
    vendor_id = fields.UUID(dump_only=True)
    email = fields.Str(dump_only=True)
    is_active = fields.Bool(dump_only=True)


class AcknowledgeOrderSchema(Schema):
    purchase_order_id = fields.UUID(required=True)
    expected_delivery_date = fields.Date(allow_none=True)


class OrderAcknowledgmentSchema(Schema):
    id = fields.UUID(dump_only=True)
    purchase_order_id = fields.UUID(dump_only=True)
    acknowledged_at = fields.DateTime(dump_only=True)
    expected_delivery_date = fields.Date(dump_only=True)


class SubmitQuoteSchema(Schema):
    rfq_id = fields.UUID(required=True)
    price = fields.Decimal(required=True, as_string=True)
    lead_time_days = fields.Int(allow_none=True)
    payment_terms = fields.Str(allow_none=True)


class ReviseQuoteSchema(Schema):
    price = fields.Decimal(required=True, as_string=True)
    lead_time_days = fields.Int(allow_none=True)
    payment_terms = fields.Str(allow_none=True)


class DeclineRfqSchema(Schema):
    reason = fields.Str(allow_none=True, load_default=None, validate=validate.Length(max=1000))


class QuotationSchema(Schema):
    id = fields.UUID(dump_only=True)
    rfq_id = fields.UUID(dump_only=True)
    price = fields.Decimal(dump_only=True, as_string=True)
    lead_time_days = fields.Int(dump_only=True)
    payment_terms = fields.Str(dump_only=True)
    submitted_at = fields.DateTime(dump_only=True)
    revised_at = fields.DateTime(dump_only=True, allow_none=True)
    revision_count = fields.Int(dump_only=True)


class RFQInvitationSchema(Schema):
    invitation_id = fields.UUID(dump_only=True)
    rfq_id = fields.UUID(dump_only=True)
    title = fields.Str(dump_only=True)
    description = fields.Str(dump_only=True, allow_none=True)
    response_deadline = fields.DateTime(dump_only=True, allow_none=True)
    rfq_status = fields.Str(dump_only=True)
    invitation_status = fields.Str(dump_only=True)
    decline_reason = fields.Str(dump_only=True, allow_none=True)
    quote = fields.Nested(QuotationSchema, dump_only=True, allow_none=True)
    can_quote = fields.Bool(dump_only=True)
    can_revise = fields.Bool(dump_only=True)
    can_decline = fields.Bool(dump_only=True)


class UploadInvoiceSchema(Schema):
    invoice_number = fields.Str(required=True)
    amount = fields.Decimal(required=True, as_string=True)
    purchase_order_id = fields.UUID(allow_none=True, load_default=None)
    subcontract_certificate_id = fields.UUID(allow_none=True, load_default=None)
    invoice_document_id = fields.UUID(allow_none=True, load_default=None)


class InvoiceUploadSchema(Schema):
    id = fields.UUID(dump_only=True)
    purchase_order_id = fields.UUID(dump_only=True)
    subcontract_certificate_id = fields.UUID(dump_only=True)
    invoice_number = fields.Str(dump_only=True)
    amount = fields.Decimal(dump_only=True, as_string=True)
    status = fields.Str(dump_only=True)


class SubmitBankingChangeSchema(Schema):
    proposed_banking_details = fields.Dict(required=True)


class RejectBankingChangeSchema(Schema):
    reason = fields.Str(required=True)


class BankingChangeRequestSchema(Schema):
    id = fields.UUID(dump_only=True)
    vendor_id = fields.UUID(dump_only=True)
    proposed_banking_details = fields.Dict(dump_only=True)
    status = fields.Str(dump_only=True)
    submitted_at = fields.DateTime(dump_only=True)
    reviewed_by = fields.UUID(dump_only=True)
    reviewed_at = fields.DateTime(dump_only=True)
    rejection_reason = fields.Str(dump_only=True)


class StaffBankingChangeRequestSchema(BankingChangeRequestSchema):
    """Review-screen view: adds what the vendor must never see."""

    vendor_name = fields.Str(dump_only=True, allow_none=True)
    current_banking_details = fields.Dict(dump_only=True, allow_none=True)
    previous_banking_details = fields.Dict(dump_only=True, allow_none=True)
