"""
Module 2 — Tender & Bid Management (Code: TBM)
Request/response schemas.
"""
from marshmallow import Schema, fields, validate

from app.modules.tbm.models import (
    TENDER_STATUSES,
    BID_DOCUMENT_TYPES,
    RFI_STATUSES,
    SUBMISSION_METHODS,
    SCOPE_ANNOTATION_TYPES,
)


class TenderSchema(Schema):
    id = fields.UUID(dump_only=True)
    opportunity_id = fields.UUID(required=True)
    reference_number = fields.Str(required=True)
    client_id = fields.UUID(allow_none=True)
    consultant_id = fields.UUID(allow_none=True)
    submission_deadline = fields.DateTime(allow_none=True)
    bid_bond_required = fields.Bool(load_default=False)
    bid_bond_amount = fields.Decimal(allow_none=True, as_string=True)
    tender_fee = fields.Decimal(allow_none=True, as_string=True)
    currency = fields.Str(load_default="NGN")
    status = fields.Str(validate=validate.OneOf(TENDER_STATUSES), dump_only=True)
    is_joint_venture = fields.Bool(load_default=False)
    estimate_locked = fields.Bool(dump_only=True)
    reopen_count = fields.Int(dump_only=True)
    created_at = fields.DateTime(dump_only=True)


class TenderBOQItemSchema(Schema):
    id = fields.UUID(dump_only=True)
    tender_id = fields.UUID(dump_only=True)
    parent_id = fields.UUID(allow_none=True)
    item_code = fields.Str(allow_none=True)
    description = fields.Str(required=True)
    unit = fields.Str(allow_none=True)
    quantity = fields.Decimal(allow_none=True, as_string=True)
    sort_order = fields.Int(load_default=0)


class ScopeItemSchema(Schema):
    id = fields.UUID(dump_only=True)
    tender_boq_item_id = fields.UUID(dump_only=True)
    annotation_type = fields.Str(required=True, validate=validate.OneOf(SCOPE_ANNOTATION_TYPES))
    text = fields.Str(required=True)


class BidDocumentSchema(Schema):
    id = fields.UUID(dump_only=True)
    tender_id = fields.UUID(dump_only=True)
    document_id = fields.UUID(allow_none=True)
    doc_type = fields.Str(required=True, validate=validate.OneOf(BID_DOCUMENT_TYPES))
    status = fields.Str(dump_only=True)


class RFISchema(Schema):
    id = fields.UUID(dump_only=True)
    tender_id = fields.UUID(dump_only=True)
    related_boq_item_id = fields.UUID(allow_none=True)
    question = fields.Str(required=True)
    due_date = fields.DateTime(allow_none=True)
    response = fields.Str(allow_none=True)
    status = fields.Str(validate=validate.OneOf(RFI_STATUSES), dump_only=True)


class RFIResponseSchema(Schema):
    response = fields.Str(required=True)


class ClarificationSchema(Schema):
    id = fields.UUID(dump_only=True)
    tender_id = fields.UUID(dump_only=True)
    addendum_number = fields.Str(required=True)
    description = fields.Str(required=True)
    issued_at = fields.DateTime(allow_none=True)
    acknowledged = fields.Bool(dump_only=True)
    affected_boq_item_ids = fields.List(fields.UUID(), allow_none=True)
    requires_reestimate = fields.Bool(load_default=False)


class ApprovalStepSchema(Schema):
    id = fields.UUID(dump_only=True)
    tender_id = fields.UUID(dump_only=True)
    step_order = fields.Int(dump_only=True)
    role_required = fields.Str(dump_only=True)
    approver_id = fields.UUID(dump_only=True)
    status = fields.Str(dump_only=True)
    comments = fields.Str(allow_none=True)


class InitiateApprovalWorkflowSchema(Schema):
    steps = fields.List(fields.Dict(), required=True)  # [{"role_required": "commercial_manager"}, ...]


class ApprovalDecisionSchema(Schema):
    decision = fields.Str(required=True, validate=validate.OneOf(("approved", "rejected")))
    comments = fields.Str(allow_none=True)


class ReopenForRevisionSchema(Schema):
    reason = fields.Str(required=True)


class TenderChecklistItemSchema(Schema):
    id = fields.UUID(dump_only=True)
    tender_id = fields.UUID(dump_only=True)
    label = fields.Str(required=True)
    is_mandatory = fields.Bool(load_default=True)
    is_complete = fields.Bool(dump_only=True)


class SubmissionSchema(Schema):
    id = fields.UUID(dump_only=True)
    tender_id = fields.UUID(dump_only=True)
    method = fields.Str(required=True, validate=validate.OneOf(SUBMISSION_METHODS))
    submitted_at = fields.DateTime(required=True)
    receipt_document_id = fields.UUID(allow_none=True)
    acknowledgment_reference = fields.Str(allow_none=True)


class JVPartnerSchema(Schema):
    id = fields.UUID(dump_only=True)
    tender_id = fields.UUID(dump_only=True)
    partner_name = fields.Str(required=True)
    scope_share_pct = fields.Decimal(required=True, as_string=True)
    financial_share_pct = fields.Decimal(required=True, as_string=True)


class TenderOutcomeSchema(Schema):
    outcome = fields.Str(required=True, validate=validate.OneOf(("won", "lost")))
    winning_price = fields.Decimal(allow_none=True, as_string=True)
    competitor_id = fields.UUID(allow_none=True)
    reason_code = fields.Str(allow_none=True)
