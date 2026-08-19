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
    # Real enforcement, not cosmetic -- checked at login
    # (app/auth/jwt_utils.py:authenticate_user); a suspended tenant's
    # users genuinely cannot log in. Set/cleared only through
    # app/platform_admin/services.py, by a real platform admin.
    is_suspended = db.Column(db.Boolean, nullable=False, default=False)


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
    department = db.Column(db.String(128), nullable=True)
    job_title = db.Column(db.String(128), nullable=True)
    avatar_document_id = db.Column(UUID(as_uuid=True), nullable=True)

    # Partial unique index, not a plain UniqueConstraint -- matches
    # migration 0043's real fix: a removed user (status="removed", a
    # soft delete) must not permanently block re-inviting the same
    # email address. Excludes removed users from the uniqueness check
    # entirely, matching the same pattern already used for
    # Invitation's own uq_invitations_one_pending_per_email.
    __table_args__ = (
        db.Index(
            "uq_users_tenant_email_active", "tenant_id", "email",
            unique=True, postgresql_where=db.text("status != 'removed'"),
        ),
    )

    role = db.relationship("Role")


class EmailTenantIndex(db.Model, UUIDPrimaryKeyMixin, AuditMixin):
    """
    Deliberately NOT tenant-scoped, deliberately NOT RLS-protected --
    exists for exactly one reason: resolving which tenant an email
    belongs to BEFORE a session has any tenant context to set. Every
    other table in this platform is protected by RLS specifically so
    that no query can ever run without tenant context; this table is
    the one narrow, intentional exception, because the problem it
    solves (login) is structurally impossible to solve any other way
    -- you cannot filter by a tenant you don't know yet.

    Contains only what that lookup needs: email, which tenant, which
    user. No password hash, no role, no permissions, nothing else --
    finding this table doesn't get anyone anything beyond "this email
    exists and belongs to this tenant," which login has to reveal
    regardless of how it's implemented (the alternative, previously
    shipped: a separate BYPASSRLS database role for the same lookup --
    functionally equivalent exposure, but one that required elevated
    database privileges that turned out not to be grantable from
    application code, and blocked login in production until this
    replaced it entirely).

    Kept in sync at the one place `User` rows are created
    (app/onboarding/services.py:signup_tenant) -- there's no ORM-level
    or trigger-level enforcement, but there's also only one call site,
    which is why it's practical to keep both writes in the same
    transaction rather than adding kept-in-sync infrastructure for
    something written from a single place.
    Known edge case, not a regression: `users.email` is only unique
    per tenant (uq_users_tenant_email), not globally, so two different
    tenants both having a user with the same email address would
    collide on this table's global unique constraint -- whichever
    signed up first keeps the index row, the second can't log in via
    this lookup. The previous BYPASSRLS approach had the same
    underlying ambiguity, just expressed differently (a raw multi-row
    SELECT with .first() picking one arbitrarily) rather than a
    constraint violation. Neither approach disambiguates the case;
    solving it for real would mean requiring a tenant identifier at
    login (a company slug, e.g.), not attempted here.
    """

    __tablename__ = "email_tenant_index"

    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
    tenant_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tenants.id"), nullable=False, index=True)


class InvitationTokenIndex(db.Model, UUIDPrimaryKeyMixin):
    """
    Deliberately NOT tenant-scoped, deliberately NOT RLS-protected --
    exactly the same reasoning as EmailTenantIndex above, applied to
    invitation tokens: resolving which tenant a token belongs to
    BEFORE any tenant context exists to look it up otherwise. See
    app/org/services.py:get_invitation_by_token for how this and the
    real, RLS-protected Invitation row are used together.
    """

    __tablename__ = "invitation_token_index"

    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    invitation_id = db.Column(UUID(as_uuid=True), nullable=False)
    tenant_id = db.Column(UUID(as_uuid=True), nullable=False)


class Project(db.Model, UUIDPrimaryKeyMixin, AuditMixin):
    __tablename__ = "projects"

    tenant_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tenants.id"), nullable=False, index=True)
    company_id = db.Column(UUID(as_uuid=True), db.ForeignKey("companies.id"), nullable=False)
    contract_id = db.Column(UUID(as_uuid=True), nullable=True)  # FK to ctm.Contract once defined
    name = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="active")
    client_id = db.Column(UUID(as_uuid=True), nullable=True)  # FK to bdc.Client (cross-module, no relationship() to avoid a circular import)
    project_manager_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)

    project_manager = db.relationship("User")


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
