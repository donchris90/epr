"""
DSAR request log -- the intake / tracking half of handling a Data
Subject Access Request. Search (services.search_by_identifier) finds
where a person's data lives; this records that a request was received,
when a response is due, what was done, and how it ended.

`actions` is an append-only list of {table, id, action, at, by}
entries written by erasure. It deliberately holds ids only, never the
erased personal data itself.
"""
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin

REQUEST_TYPES = ("access", "correction", "erasure", "restriction", "objection", "portability")
REQUEST_STATUSES = ("open", "in_progress", "completed", "rejected")
RESPONSE_DAYS = 30  # matches the commitment in the public Privacy Policy


class DSARRequest(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    __tablename__ = "dsar_requests"

    request_type = db.Column(db.String(16), nullable=False)
    subject_name = db.Column(db.String(255), nullable=False)
    subject_email = db.Column(db.String(255), nullable=True)
    subject_phone = db.Column(db.String(64), nullable=True)
    details = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(16), nullable=False, default="open")
    received_at = db.Column(db.DateTime(timezone=True), nullable=False)
    due_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    resolved_by = db.Column(UUID(as_uuid=True), nullable=True)
    resolution_notes = db.Column(db.Text, nullable=True)
    actions = db.Column(JSONB, nullable=False, default=list)

    __table_args__ = (
        db.CheckConstraint(f"request_type IN {REQUEST_TYPES}", name="ck_dsar_requests_type"),
        db.CheckConstraint(f"status IN {REQUEST_STATUSES}", name="ck_dsar_requests_status"),
    )
