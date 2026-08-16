"""
Module 24 — Mobile Field App (Code: MFA)
Request/response schemas.
"""
from marshmallow import Schema, fields, validate

from app.modules.mfa.models import SYNC_OPERATIONS, TARGET_ENTITY_TYPES, SYNC_STATUSES


class SyncEntryInputSchema(Schema):
    client_record_id = fields.UUID(required=True)
    target_module = fields.Str(required=True)
    target_entity_type = fields.Str(required=True, validate=validate.OneOf(TARGET_ENTITY_TYPES))
    operation = fields.Str(load_default="create", validate=validate.OneOf(SYNC_OPERATIONS))
    payload = fields.Dict(required=True)
    device_timestamp = fields.DateTime(allow_none=True)


class SyncBatchInputSchema(Schema):
    device_id = fields.Str(required=True)
    entries = fields.List(fields.Nested(SyncEntryInputSchema), required=True)


class SyncQueueEntrySchema(Schema):
    id = fields.UUID(dump_only=True)
    client_record_id = fields.UUID(dump_only=True)
    target_entity_type = fields.Str(dump_only=True)
    status = fields.Str(validate=validate.OneOf(SYNC_STATUSES), dump_only=True)
    server_record_id = fields.UUID(dump_only=True, allow_none=True)
    synced_at = fields.DateTime(dump_only=True)
    rejection_reason = fields.Str(dump_only=True)


class ResolveConflictSchema(Schema):
    resolution = fields.Dict(required=True)


class ConflictRecordSchema(Schema):
    id = fields.UUID(dump_only=True)
    sync_queue_entry_id = fields.UUID(dump_only=True)
    conflict_type = fields.Str(dump_only=True)
    client_payload = fields.Dict(dump_only=True)
    server_current_state = fields.Dict(dump_only=True, allow_none=True)
    status = fields.Str(dump_only=True)
    resolution = fields.Dict(dump_only=True, allow_none=True)
