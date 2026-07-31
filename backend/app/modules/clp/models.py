"""
Module 22 — Client Portal (Code: CLP)
SRS Section 4.22.

Gives the paying client (or asset owner) self-service visibility and
approval capability without needing full platform access.

Key Data Entities (SRS 4.22): ClientPortalUser, ClientApprovalAction --
otherwise reads from core project entities with a restricted,
client-scoped view.

Design notes:
  - `ClientProjectAssignment` is not in the SRS's named entity list but
    IS the actual source of truth the business rule depends on: "a
    Client Portal user can never view another client's project data...
    regardless of any misconfiguration elsewhere in the permission
    matrix" requires somewhere independent of the general RBAC/
    permission system to check against. This table is that somewhere --
    services.assert_client_project_access checks it directly, on every
    single data-returning function in this module, unconditionally.
    This is deliberately a SEPARATE check from `@require_permission`,
    not a replacement for it: even a client user holding a
    (misconfigured) `clp:read` grant for every project still gets
    filtered down to only their assigned ones here, because this check
    doesn't consult the permission system at all -- it consults this
    table.
  - `ClientRequest` is not in the SRS's named entity list but is what
    CLP-07 ("Submit Requests... tracked to resolution") needs to exist
    at all.
  - CLP-06's "without exposing internal cost data" is satisfied by
    construction for the schedule view: it reads Module 5's Activity
    data, which has no cost fields on it at all (cost lives on
    Module 3's CBS, referenced only via WBSNode.cbs_line_item_id) --
    the client-facing schedule schema explicitly excludes that
    reference field too, so there's no cost-code breadcrumb for a
    client to follow even indirectly.
"""
from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin


APPROVAL_ACTION_TYPES = ("variation_order", "progress_certificate")
APPROVAL_DECISIONS = ("approved", "rejected")
CLIENT_REQUEST_TYPES = ("rfi", "service_request")
CLIENT_REQUEST_STATUSES = ("open", "in_progress", "resolved")


class ClientPortalUser(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """The external client/asset-owner user -- deliberately NOT the
    same table as the internal `users` model; a client user should
    never be reachable through internal user lookups."""

    __tablename__ = "clp_portal_users"

    client_organization_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    __table_args__ = (db.UniqueConstraint("tenant_id", "email", name="uq_clp_portal_users_tenant_email"),)


class ClientProjectAssignment(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """CLP-08: the actual scope grant. A client user has access to
    exactly the projects with a row here -- nothing else, regardless of
    what any permission grant might otherwise suggest (business rule,
    see module docstring)."""

    __tablename__ = "clp_project_assignments"

    client_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("clp_portal_users.id"), nullable=False, index=True)
    project_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)

    __table_args__ = (
        db.UniqueConstraint("client_user_id", "project_id", name="uq_clp_assignment_user_project"),
    )


class ClientApprovalAction(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """CLP-03, CLP-05: a client's online approval of a Variation Order
    (Module 18) or Progress Certificate (Module 18), with a recorded
    digital approval and timestamp -- the client-facing audit trail of
    the decision, separate from (but linked to) the record it decided."""

    __tablename__ = "clp_approval_actions"

    client_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("clp_portal_users.id"), nullable=False, index=True)
    action_type = db.Column(db.String(24), nullable=False)
    target_id = db.Column(UUID(as_uuid=True), nullable=False)  # bil_variation_orders.id or bil_progress_certificates.id
    decision = db.Column(db.String(16), nullable=False)
    decided_at = db.Column(db.DateTime(timezone=True), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    __table_args__ = (
        db.CheckConstraint(f"action_type IN {APPROVAL_ACTION_TYPES}", name="ck_clp_approval_action_type"),
        db.CheckConstraint(f"decision IN {APPROVAL_DECISIONS}", name="ck_clp_approval_decision"),
    )


class ClientRequest(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """CLP-07: an RFI to the contractor, or a service request for
    asset-owner clients, tracked to resolution."""

    __tablename__ = "clp_client_requests"

    client_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("clp_portal_users.id"), nullable=False, index=True)
    project_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    request_type = db.Column(db.String(24), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="open")
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    response = db.Column(db.Text, nullable=True)

    __table_args__ = (
        db.CheckConstraint(f"request_type IN {CLIENT_REQUEST_TYPES}", name="ck_clp_request_type"),
        db.CheckConstraint(f"status IN {CLIENT_REQUEST_STATUSES}", name="ck_clp_request_status"),
    )
