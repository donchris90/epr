"""
Module 27 — Subcontractor Portal (Code: SCP)

Gives subcontractors self-service visibility and submission capability
without needing full platform access -- the same shape as Module 22
(Client Portal) and Module 23 (Vendor Portal), completing the pattern:
every external party this platform deals with (client, vendor,
subcontractor) now has its own scoped portal.

Design notes:
  - Like VNP, a subcontractor portal user belongs to exactly ONE
    subcontractor (`SubcontractorPortalUser.subcontractor_id`), so the
    defense-in-depth ownership check is the simple one-to-one shape,
    not CLP's many-to-many client-to-project scoping.
  - No new tables beyond the portal user itself. Module 12's own
    SubcontractProgressEntry (SUB-03) and SubcontractClaim (SUB-07)
    were already designed anticipating subcontractor-submitted data --
    SubcontractProgressEntry.submitted_by is literally documented as
    "the subcontractor's representative" -- so this portal writes
    directly to those existing tables through ownership-checked
    service functions, exactly the way VNP-02's quote submission
    writes directly to PRC's existing RFQQuotation rather than
    duplicating it. Reuse over redesign, the same principle this
    entire portal follows.
"""
from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin


class SubcontractorPortalUser(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """SCP's one named entity -- a portal login scoped to exactly one
    subcontractor (Module 12's Subcontractor, loose reference).

    `password_hash` (migration 0049_scp_vnp_auth) is nullable: a
    portal user created before a password is set simply cannot log in
    yet -- a real, visible state, not a crash. Same Argon2id scheme as
    users.password_hash and clp_portal_users.password_hash (see
    app/auth/jwt_utils.py's shared hash_password/verify_password)."""

    __tablename__ = "scp_portal_users"

    subcontractor_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)  # sub_subcontractors.id, loose reference
    email = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    password_hash = db.Column(db.String(255), nullable=True)

    __table_args__ = (db.UniqueConstraint("tenant_id", "email", name="uq_scp_portal_users_tenant_email"),)


class SubcontractorPortalEmailIndex(db.Model, UUIDPrimaryKeyMixin):
    """Deliberately NOT tenant-scoped, deliberately NOT RLS-protected --
    same reasoning as EmailTenantIndex/ClientPortalEmailIndex: a
    subcontractor logging in has no tenant context yet. Allows the
    same email across multiple tenants (a subcontractor working with
    more than one contractor is ordinary) -- login resolves every
    matching row and tries each tenant's password in turn (see
    services.py:authenticate_subcontractor_user)."""

    __tablename__ = "scp_email_index"

    email = db.Column(db.String(255), nullable=False, index=True)
    portal_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("scp_portal_users.id"), nullable=False)
    tenant_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tenants.id"), nullable=False, index=True)

    __table_args__ = (db.UniqueConstraint("email", "tenant_id", name="uq_scp_email_index_email_tenant"),)
