"""
Module 1 — Business Development & CRM (Code: BDC)
Request/response schemas.
"""
from marshmallow import Schema, fields, validate

from app.modules.bdc.models import OPPORTUNITY_STAGES, LEAD_STATUSES, BID_NO_BID_DECISIONS


class ClientSchema(Schema):
    id = fields.UUID(dump_only=True)
    name = fields.Str(required=True)
    billing_address = fields.Str(allow_none=True)
    billing_email = fields.Email(allow_none=True)
    notes = fields.Str(allow_none=True)
    created_at = fields.DateTime(dump_only=True)


class LeadSchema(Schema):
    id = fields.UUID(dump_only=True)
    client_id = fields.UUID(allow_none=True)
    name = fields.Str(required=True)
    source = fields.Str(allow_none=True)
    estimated_value = fields.Decimal(allow_none=True, as_string=True)
    currency = fields.Str(load_default="NGN")
    probability_pct = fields.Decimal(allow_none=True, as_string=True)
    status = fields.Str(validate=validate.OneOf(LEAD_STATUSES), dump_only=True)
    created_at = fields.DateTime(dump_only=True)


class OpportunitySchema(Schema):
    id = fields.UUID(dump_only=True)
    lead_id = fields.UUID(allow_none=True)
    client_id = fields.UUID(required=True)
    name = fields.Str(required=True)
    stage = fields.Str(validate=validate.OneOf(OPPORTUNITY_STAGES))
    estimated_value = fields.Decimal(allow_none=True, as_string=True)
    currency = fields.Str(load_default="NGN")
    submission_deadline = fields.DateTime(allow_none=True)
    bid_no_bid_decision = fields.Str(dump_only=True)
    contract_id = fields.UUID(dump_only=True)
    created_at = fields.DateTime(dump_only=True)


class StageTransitionSchema(Schema):
    new_stage = fields.Str(required=True, validate=validate.OneOf(OPPORTUNITY_STAGES))


class BidNoBidDecisionSchema(Schema):
    decision = fields.Str(required=True, validate=validate.OneOf(BID_NO_BID_DECISIONS))
    scorecard = fields.Dict(required=True)
    rationale = fields.Str(required=True)
    reason_code = fields.Str(allow_none=True)


class WinLossRecordSchema(Schema):
    id = fields.UUID(dump_only=True)
    opportunity_id = fields.UUID(required=True)
    outcome = fields.Str(required=True, validate=validate.OneOf(("won", "lost")))
    winning_price = fields.Decimal(allow_none=True, as_string=True)
    competitor_id = fields.UUID(allow_none=True)
    reason_code = fields.Str(allow_none=True)
    sector = fields.Str(allow_none=True)
    value_band = fields.Str(allow_none=True)


class CompetitorSchema(Schema):
    id = fields.UUID(dump_only=True)
    name = fields.Str(required=True)
    notes = fields.Str(allow_none=True)
    known_win_count = fields.Int(dump_only=True)
    known_loss_count = fields.Int(dump_only=True)


class ConsultantSchema(Schema):
    id = fields.UUID(dump_only=True)
    name = fields.Str(required=True)
    discipline = fields.Str(allow_none=True)
    relationship_notes = fields.Str(allow_none=True)


class GovernmentAgencySchema(Schema):
    id = fields.UUID(dump_only=True)
    name = fields.Str(required=True)
    jurisdiction = fields.Str(allow_none=True)
    tender_pattern_notes = fields.Str(allow_none=True)
