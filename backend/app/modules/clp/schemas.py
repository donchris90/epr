"""
Module 22 — Client Portal (Code: CLP)
Request/response schemas.
"""
from marshmallow import Schema, fields, validate

from app.modules.clp.models import APPROVAL_DECISIONS, CLIENT_REQUEST_TYPES, CLIENT_REQUEST_STATUSES


class ClientPortalUserInputSchema(Schema):
    client_organization_name = fields.Str(required=True)
    email = fields.Str(required=True)
    # load_only + not a model column -- popped off in the route and
    # passed to services.set_client_password separately, since the
    # model stores password_hash, never the plaintext value itself.
    password = fields.Str(required=True, load_only=True, validate=validate.Length(min=8))


class ClientPortalUserSchema(Schema):
    id = fields.UUID(dump_only=True)
    client_organization_name = fields.Str(dump_only=True)
    email = fields.Str(dump_only=True)
    is_active = fields.Bool(dump_only=True)
    can_login = fields.Method("_can_login", dump_only=True)

    def _can_login(self, obj):
        return bool(getattr(obj, "password_hash", None))


class ClientLoginSchema(Schema):
    email = fields.Str(required=True)
    password = fields.Str(required=True)


class ClientTokenSchema(Schema):
    access_token = fields.Str(dump_only=True)
    refresh_token = fields.Str(dump_only=True)


class ChangeClientPasswordSchema(Schema):
    current_password = fields.Str(required=True)
    new_password = fields.Str(required=True, validate=validate.Length(min=8))


class ClientProjectAssignmentInputSchema(Schema):
    project_id = fields.UUID(required=True)


class ClientProjectAssignmentSchema(Schema):
    id = fields.UUID(dump_only=True)
    client_user_id = fields.UUID(dump_only=True)
    project_id = fields.UUID(dump_only=True)


class ApprovalDecisionSchema(Schema):
    project_id = fields.UUID(required=True)
    decision = fields.Str(required=True, validate=validate.OneOf(APPROVAL_DECISIONS))
    notes = fields.Str(allow_none=True)


class ClientApprovalActionSchema(Schema):
    id = fields.UUID(dump_only=True)
    action_type = fields.Str(dump_only=True)
    target_id = fields.UUID(dump_only=True)
    decision = fields.Str(dump_only=True)
    decided_at = fields.DateTime(dump_only=True)


class ClientRequestInputSchema(Schema):
    project_id = fields.UUID(required=True)
    request_type = fields.Str(required=True, validate=validate.OneOf(CLIENT_REQUEST_TYPES))
    description = fields.Str(required=True)


class ResolveClientRequestSchema(Schema):
    response = fields.Str(required=True)


class ClientRequestSchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(dump_only=True)
    request_type = fields.Str(dump_only=True)
    description = fields.Str(dump_only=True)
    status = fields.Str(validate=validate.OneOf(CLIENT_REQUEST_STATUSES), dump_only=True)
    response = fields.Str(dump_only=True)
    submitted_at = fields.DateTime(dump_only=True)
    resolved_at = fields.DateTime(dump_only=True)


# --- Client-safe read views ------------------------------------------------------
# Deliberately separate, narrower schemas from the internal ones used
# by projects/documents/bil -- every field below was chosen because a
# client should see it; nothing is included "because the underlying
# row has it". See docs/CLIENT_PORTAL_GAPS.md for the fields left out
# on purpose (internal cost codes, margins, other clients' data).

class ClientProjectSummarySchema(Schema):
    id = fields.UUID(dump_only=True)
    name = fields.Str(dump_only=True)
    status = fields.Str(dump_only=True)
    start_date = fields.Date(dump_only=True)
    end_date = fields.Date(dump_only=True)


class ClientProjectDetailSchema(ClientProjectSummarySchema):
    contract_value = fields.Decimal(dump_only=True, as_string=True)
    currency = fields.Str(dump_only=True)


class ClientDocumentSchema(Schema):
    id = fields.UUID(dump_only=True)
    original_filename = fields.Str(dump_only=True)
    doc_type = fields.Str(dump_only=True)
    status = fields.Str(dump_only=True)
    created_at = fields.DateTime(dump_only=True)


class ClientCertificateSchema(Schema):
    id = fields.UUID(dump_only=True)
    certificate_number = fields.Str(dump_only=True)
    period_start = fields.Date(dump_only=True)
    period_end = fields.Date(dump_only=True)
    gross_certified_amount = fields.Decimal(dump_only=True, as_string=True)
    retention_withheld = fields.Decimal(dump_only=True, as_string=True)
    net_payable = fields.Decimal(dump_only=True, as_string=True)
    status = fields.Str(dump_only=True)


class ClientVariationOrderSchema(Schema):
    id = fields.UUID(dump_only=True)
    description = fields.Str(dump_only=True)
    varied_quantity = fields.Decimal(dump_only=True, as_string=True)
    varied_rate = fields.Decimal(dump_only=True, as_string=True)
    status = fields.Str(dump_only=True)


class ClientInvoiceSchema(Schema):
    id = fields.UUID(dump_only=True)
    certificate_id = fields.UUID(dump_only=True)
    certificate_number = fields.Str(dump_only=True)
    status = fields.Str(dump_only=True)
    due_date = fields.Date(dump_only=True)
    net_payable = fields.Decimal(dump_only=True, as_string=True)
    paid_amount = fields.Decimal(dump_only=True, as_string=True)
