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
    subcontractor (Module 12's Subcontractor, loose reference)."""

    __tablename__ = "scp_portal_users"

    subcontractor_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)  # sub_subcontractors.id, loose reference
    email = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    __table_args__ = (db.UniqueConstraint("tenant_id", "email", name="uq_scp_portal_users_tenant_email"),)
