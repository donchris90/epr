"""
Shared model mixins, per SRS Section 5.1 (Schema Design Principles):

- UUID primary keys (not auto-increment) — supports offline mobile record
  creation without server round-trips, and avoids leaking sequence-based
  record counts across tenants.
- Every tenant-scoped table carries tenant_id + a matching Postgres
  Row-Level Security policy (created in the Alembic migration, not here —
  RLS is DDL, not something the ORM can express).
- created_at / updated_at / created_by / updated_by audit columns on
  every table.
- Soft deletes (deleted_at) for records with downstream financial or
  contractual implications.
"""
import uuid

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.extensions import db


class UUIDPrimaryKeyMixin:
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TenantMixin:
    """
    Every tenant-scoped table must mix this in. The corresponding Alembic
    migration must ALSO create:

        ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;
        CREATE POLICY tenant_isolation ON <table>
          USING (tenant_id = current_setting('app.tenant_id')::uuid);

    per SRS Section 5.5. The ORM-level column below is necessary but not
    sufficient — RLS is the actual enforcement boundary (Section 3.4).
    """

    tenant_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)


class AuditMixin:
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_by = db.Column(UUID(as_uuid=True), nullable=True)
    updated_by = db.Column(UUID(as_uuid=True), nullable=True)


class SoftDeleteMixin:
    """For records with downstream financial/contractual implications
    (SRS Section 5.1) — hard deletes are reserved for genuinely transient,
    never-submitted draft data only."""

    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
