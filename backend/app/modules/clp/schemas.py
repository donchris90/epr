"""
Module 22 — Client Portal (Code: CLP)
Request/response schemas.
"""
from marshmallow import Schema, fields, validate

from app.modules.clp.models import APPROVAL_DECISIONS, CLIENT_REQUEST_TYPES, CLIENT_REQUEST_STATUSES


class ClientPortalUserInputSchema(Schema):
    client_organization_name = fields.Str(required=True)
    email = fields.Str(required=True)


class ClientPortalUserSchema(Schema):
    id = fields.UUID(dump_only=True)
    client_organization_name = fields.Str(dump_only=True)
    email = fields.Str(dump_only=True)
    is_active = fields.Bool(dump_only=True)


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
