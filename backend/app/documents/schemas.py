"""
Document storage schemas.
"""
from marshmallow import Schema, fields


class CreateUploadRequestSchema(Schema):
    original_filename = fields.Str(required=True)
    content_type = fields.Str(allow_none=True, load_default=None)
    project_id = fields.UUID(allow_none=True, load_default=None)
    doc_type = fields.Str(allow_none=True, load_default=None)


class UploadRequestResponseSchema(Schema):
    id = fields.UUID(dump_only=True)
    upload_url = fields.Str(dump_only=True)
    status = fields.Str(dump_only=True)


class DocumentSchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(dump_only=True, allow_none=True)
    doc_type = fields.Str(dump_only=True, allow_none=True)
    original_filename = fields.Str(dump_only=True, allow_none=True)
    content_type = fields.Str(dump_only=True, allow_none=True)
    size_bytes = fields.Int(dump_only=True, allow_none=True)
    status = fields.Str(dump_only=True)
    created_at = fields.DateTime(dump_only=True)


class DocumentWithUrlSchema(DocumentSchema):
    download_url = fields.Str(dump_only=True, allow_none=True)
