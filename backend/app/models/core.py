"""
Core cross-module entities (SRS Section 5.2). These form the backbone of
traceability described in Section 2.1 and are referenced by virtually
every one of the 25 module bounded contexts.
"""
import uuid

from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.extensions import db
from app.models.base import UUIDPrimaryKeyMixin, AuditMixin


class Tenant(db.Model, UUIDPrimaryKeyMixin, AuditMixin):
    __tablename__ = "tenants"

    name = db.Column(db.String(255), nullable=False)
    subscription_plan = db.Column(db.String(64), nullable=False, default="standard")
    region = db.Column(db.String(64), nullable=True)


class Company(db.Model, UUIDPrimaryKeyMixin, AuditMixin):
    __tablename__ = "companies"

    tenant_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tenants.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    base_currency = db.Column(db.String(3), nullable=False, default="NGN")


class Role(db.Model, UUIDPrimaryKeyMixin, AuditMixin):
    __tablename__ = "roles"

    tenant_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tenants.id"), nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)
    # module:action permission strings, e.g. "procurement:approve" (SRS 8.1)
    permission_set = db.Column(JSONB, nullable=False, default=list)


class User(db.Model, UUIDPrimaryKeyMixin, AuditMixin):
    __tablename__ = "users"

    tenant_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tenants.id"), nullable=False, index=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role_id = db.Column(UUID(as_uuid=True), db.ForeignKey("roles.id"), nullable=True)
    status = db.Column(db.String(32), nullable=False, default="active")

    __table_args__ = (db.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),)


class Project(db.Model, UUIDPrimaryKeyMixin, AuditMixin):
    __tablename__ = "projects"

    tenant_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tenants.id"), nullable=False, index=True)
    company_id = db.Column(UUID(as_uuid=True), db.ForeignKey("companies.id"), nullable=False)
    contract_id = db.Column(UUID(as_uuid=True), nullable=True)  # FK to ctm.Contract once defined
    name = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="active")


class Document(db.Model, UUIDPrimaryKeyMixin, AuditMixin):
    """Referenced by virtually every module (SRS Section 5.2).

    Lifecycle (see app/documents/services.py): a row is created in
    status="pending" when an upload is first requested, alongside a
    presigned S3 PUT URL the client uploads bytes to directly -- Flask
    itself never touches file bytes, only S3 does. The row only moves
    to status="uploaded" once services.confirm_upload has verified via
    a real HEAD request that the object actually exists in S3 with a
    nonzero size; a client claiming it uploaded something is not
    sufficient on its own; the object is checked for."""

    __tablename__ = "documents"

    tenant_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tenants.id"), nullable=False, index=True)
    project_id = db.Column(UUID(as_uuid=True), db.ForeignKey("projects.id"), nullable=True, index=True)
    file_key = db.Column(db.String(512), nullable=False)  # S3 object key
    doc_type = db.Column(db.String(64), nullable=True)

    original_filename = db.Column(db.String(255), nullable=True)
    content_type = db.Column(db.String(128), nullable=True)
    size_bytes = db.Column(db.BigInteger, nullable=True)  # set on confirm, from S3's own HEAD response, not client-supplied
    status = db.Column(db.String(16), nullable=False, default="pending")  # pending | uploaded | failed
    uploaded_by = db.Column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        db.CheckConstraint("status IN ('pending','uploaded','failed')", name="ck_documents_status"),
    )
