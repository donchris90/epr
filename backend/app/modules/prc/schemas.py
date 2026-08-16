"""
Module 7 — Procurement (Code: PRC)
Request/response schemas.
"""
from marshmallow import Schema, fields, validate

from app.modules.prc.models import (
    VENDOR_STATUSES,
    RFQ_STATUSES,
    PR_STATUSES,
    GRN_CONDITIONS,
)


class VendorSchema(Schema):
    id = fields.UUID(dump_only=True)
    name = fields.Str(required=True)
    tax_registration_number = fields.Str(allow_none=True)
    banking_details = fields.Dict(allow_none=True)
    categories_supplied = fields.List(fields.Str(), allow_none=True)
    status = fields.Str(validate=validate.OneOf(VENDOR_STATUSES), dump_only=True)


class VendorComplianceDocumentSchema(Schema):
    id = fields.UUID(dump_only=True)
    vendor_id = fields.UUID(dump_only=True)
    document_id = fields.UUID(allow_none=True)
    doc_type = fields.Str(required=True)
    valid_until = fields.Date(allow_none=True)


class RFQSchema(Schema):
    id = fields.UUID(dump_only=True)
    title = fields.Str(required=True)
    description = fields.Str(allow_none=True)
    response_deadline = fields.DateTime(allow_none=True)
    status = fields.Str(validate=validate.OneOf(RFQ_STATUSES), dump_only=True)


class RFQInvitationSchema(Schema):
    id = fields.UUID(dump_only=True)
    rfq_id = fields.UUID(dump_only=True)
    vendor_id = fields.UUID(required=True)
    status = fields.Str(dump_only=True)


class RFQQuotationSchema(Schema):
    id = fields.UUID(dump_only=True)
    rfq_id = fields.UUID(dump_only=True)
    vendor_id = fields.UUID(required=True)
    price = fields.Decimal(required=True, as_string=True)
    lead_time_days = fields.Int(allow_none=True)
    payment_terms = fields.Str(allow_none=True)
    submitted_at = fields.DateTime(allow_none=True)


class PurchaseRequestSchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(allow_none=True)
    cbs_line_item_id = fields.UUID(allow_none=True)
    description = fields.Str(required=True)
    quantity = fields.Decimal(required=True, as_string=True)
    unit = fields.Str(allow_none=True)
    estimated_unit_cost = fields.Decimal(allow_none=True, as_string=True)
    estimated_total = fields.Decimal(allow_none=True, as_string=True)
    status = fields.Str(validate=validate.OneOf(PR_STATUSES), dump_only=True)
    budget_override = fields.Bool(dump_only=True)


class SubmitPurchaseRequestSchema(Schema):
    remaining_budget = fields.Decimal(allow_none=True, as_string=True, load_default=None)
    override = fields.Bool(load_default=False)
    override_reason = fields.Str(allow_none=True)


class PurchaseOrderLineInputSchema(Schema):
    boq_item_id = fields.UUID(allow_none=True)
    cbs_line_item_id = fields.UUID(allow_none=True)
    material_item_id = fields.UUID(allow_none=True)
    description = fields.Str(required=True)
    quantity = fields.Decimal(required=True, as_string=True)
    unit = fields.Str(allow_none=True)
    unit_price = fields.Decimal(required=True, as_string=True)


class PurchaseOrderSchema(Schema):
    id = fields.UUID(dump_only=True)
    purchase_request_id = fields.UUID(allow_none=True)
    rfq_quotation_id = fields.UUID(allow_none=True)
    vendor_id = fields.UUID(required=True)
    po_number = fields.Str(required=True)
    status = fields.Str(dump_only=True)
    total_value = fields.Decimal(required=True, as_string=True)
    currency = fields.Str(load_default="NGN")
    is_blanket = fields.Bool(load_default=False)
    compliance_waiver = fields.Bool(dump_only=True)
    lines = fields.List(fields.Nested(PurchaseOrderLineInputSchema), load_only=True, required=False)


class PurchaseOrderLineSchema(Schema):
    id = fields.UUID(dump_only=True)
    purchase_order_id = fields.UUID(dump_only=True)
    material_item_id = fields.UUID(dump_only=True)
    description = fields.Str(dump_only=True)
    quantity = fields.Decimal(dump_only=True, as_string=True)
    unit_price = fields.Decimal(dump_only=True, as_string=True)
    line_total = fields.Decimal(dump_only=True, as_string=True)
    quantity_received = fields.Decimal(dump_only=True, as_string=True)


class InitiatePOApprovalSchema(Schema):
    thresholds = fields.List(fields.Dict(), required=True)


class POApprovalStepSchema(Schema):
    id = fields.UUID(dump_only=True)
    step_order = fields.Int(dump_only=True)
    role_required = fields.Str(dump_only=True)
    value_threshold = fields.Decimal(dump_only=True, as_string=True, allow_none=True)
    status = fields.Str(dump_only=True)
    comments = fields.Str(dump_only=True, allow_none=True)


class POApprovalDecisionSchema(Schema):
    decision = fields.Str(required=True, validate=validate.OneOf(("approved", "rejected")))
    comments = fields.Str(allow_none=True)


class IssuePOSchema(Schema):
    waiver = fields.Bool(load_default=False)
    waiver_reason = fields.Str(allow_none=True)


class GoodsReceiptLineInputSchema(Schema):
    po_line_id = fields.UUID(required=True)
    quantity_received = fields.Decimal(required=True, as_string=True)
    condition = fields.Str(load_default="good", validate=validate.OneOf(GRN_CONDITIONS))
    discrepancy_notes = fields.Str(allow_none=True)


class GoodsReceiptNoteSchema(Schema):
    id = fields.UUID(dump_only=True)
    purchase_order_id = fields.UUID(required=True)
    warehouse_id = fields.UUID(allow_none=True)
    received_at = fields.DateTime(allow_none=True)
    status = fields.Str(dump_only=True)
    lines = fields.List(fields.Nested(GoodsReceiptLineInputSchema), load_default=list)


class InvoiceMatchRequestSchema(Schema):
    goods_receipt_note_id = fields.UUID(allow_none=True, load_default=None)
    vendor_invoice_reference = fields.Str(required=True)
    invoice_amount = fields.Decimal(required=True, as_string=True)


class InvoiceMatchSchema(Schema):
    id = fields.UUID(dump_only=True)
    purchase_order_id = fields.UUID(dump_only=True)
    vendor_invoice_reference = fields.Str(dump_only=True)
    invoice_amount = fields.Decimal(dump_only=True, as_string=True)
    po_amount = fields.Decimal(dump_only=True, as_string=True)
    grn_amount = fields.Decimal(dump_only=True, as_string=True)
    match_status = fields.Str(dump_only=True)
    released_for_payment = fields.Bool(dump_only=True)


class MatchExceptionSchema(Schema):
    reason = fields.Str(required=True)


class VendorPerformanceRecordSchema(Schema):
    id = fields.UUID(dump_only=True)
    vendor_id = fields.UUID(dump_only=True)
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)
    on_time_delivery_rate = fields.Decimal(allow_none=True, as_string=True)
    quality_rejection_rate = fields.Decimal(allow_none=True, as_string=True)
    price_competitiveness_score = fields.Decimal(allow_none=True, as_string=True)


class SupplierRatingSchema(Schema):
    id = fields.UUID(dump_only=True)
    vendor_id = fields.UUID(dump_only=True)
    rating_period = fields.Str(allow_none=True)
    scorecard = fields.Dict(required=True)
    overall_score = fields.Decimal(allow_none=True, as_string=True)
