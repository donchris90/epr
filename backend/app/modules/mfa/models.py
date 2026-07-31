"""
Module 24 — Mobile Field App (Code: MFA)
SRS Section 4.24.

The primary interface for site-based roles; offline-first by design.
The actual mobile client (local SQLite store, camera/QR capture, offline
UI) is out of scope for this backend -- what belongs here, and what
this module implements for real, is the SERVER SIDE of the sync
protocol: how a batch of offline-captured records gets reconciled
against the live database when connectivity returns.

Key Data Entities (SRS 4.24): mirrors server-side entities on the
device (out of scope here -- that's the mobile client's local store,
not a server-side table) plus `SyncQueueEntry` and `ConflictRecord` for
offline operation management, which ARE server-side and are what this
module actually implements.

Design notes:
  - Business rule (SRS 4.24): no mobile-captured record is considered
    final/official until successfully synced and accepted by the
    server. `SyncQueueEntry.status` starts at "pending" and only a
    successful services.process_sync_entry call moves it to "synced" --
    there is no code path that marks a record synced without the
    server actually having validated and committed it.
  - Business rule (SRS 4.24): conflicts are never silently discarded.
    Every entry that fails to apply cleanly becomes a `ConflictRecord`,
    not a dropped or silently-retried entry -- services.py has no
    code path that discards a failed sync entry without creating one.
  - `client_record_id` (the UUID the mobile device generated offline,
    before ever talking to the server) is the idempotency key: a
    device can safely resubmit the same batch after a dropped
    connection without creating duplicate records, because the server
    checks for an existing SyncQueueEntry with that client_record_id
    before processing.
  - This pass implements REAL dispatch for two concrete target entity
    types (HSE NearMiss reports and Asset inspections) as representative
    examples of genuine field-captured data -- not a fake or mocked
    dispatcher. Extending to further target types (progress entries,
    material receipts, checklist completions) is a matter of adding
    more dispatch cases to the same real mechanism, not a different
    architecture.
"""
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin


SYNC_OPERATIONS = ("create", "update")
SYNC_STATUSES = ("pending", "synced", "conflict", "rejected")
TARGET_ENTITY_TYPES = ("hse_near_miss", "ast_asset_inspection")
CONFLICT_TYPES = ("concurrent_update", "validation_failure", "permission_denied")
CONFLICT_STATUSES = ("unresolved", "resolved")


class SyncQueueEntry(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """MFA-08, MFA-09: one offline-captured operation, its sync status,
    and (once synced) the server-side record it became. Business rule
    -- `status` only ever reaches "synced" via a real, successful
    server-side commit."""

    __tablename__ = "mfa_sync_queue_entries"

    device_id = db.Column(db.String(128), nullable=False, index=True)
    client_record_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)  # idempotency key
    target_module = db.Column(db.String(32), nullable=False)  # e.g. "HSE", "AST"
    target_entity_type = db.Column(db.String(32), nullable=False)
    operation = db.Column(db.String(16), nullable=False, default="create")
    payload = db.Column(JSONB, nullable=False)
    device_timestamp = db.Column(db.DateTime(timezone=True), nullable=True)  # when captured, per MFA-10 offline duration tracking

    status = db.Column(db.String(16), nullable=False, default="pending", index=True)
    server_record_id = db.Column(UUID(as_uuid=True), nullable=True)  # set once genuinely committed
    synced_at = db.Column(db.DateTime(timezone=True), nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)

    __table_args__ = (
        db.CheckConstraint(f"operation IN {SYNC_OPERATIONS}", name="ck_mfa_sync_operation"),
        db.CheckConstraint(f"status IN {SYNC_STATUSES}", name="ck_mfa_sync_status"),
        db.UniqueConstraint("tenant_id", "client_record_id", name="uq_mfa_sync_tenant_client_record"),
    )


class ConflictRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """Business rule -- every SyncQueueEntry that cannot apply cleanly
    becomes one of these, never a silent drop. Preserves BOTH sides:
    the client's original payload and the server's state at the moment
    of conflict, so a human reviewer sees exactly what disagreed."""

    __tablename__ = "mfa_conflict_records"

    sync_queue_entry_id = db.Column(UUID(as_uuid=True), db.ForeignKey("mfa_sync_queue_entries.id"), nullable=False, index=True)
    conflict_type = db.Column(db.String(24), nullable=False)
    client_payload = db.Column(JSONB, nullable=False)
    server_current_state = db.Column(JSONB, nullable=True)  # null for validation_failure (nothing to compare against)
    status = db.Column(db.String(16), nullable=False, default="unresolved", index=True)
    resolution = db.Column(JSONB, nullable=True)
    resolved_by = db.Column(UUID(as_uuid=True), nullable=True)
    resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        db.CheckConstraint(f"conflict_type IN {CONFLICT_TYPES}", name="ck_mfa_conflict_type"),
        db.CheckConstraint(f"status IN {CONFLICT_STATUSES}", name="ck_mfa_conflict_status"),
    )
