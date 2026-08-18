"""
Organization user management -- real invitations, real seat-limit
enforcement against the tenant's actual subscription plan
(app/billing/models.py:SubscriptionPlan.seat_limit), and user
management actions (suspend/reactivate/remove). Base path for routes:
/v1/org.
"""
from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db
from app.models.base import UUIDPrimaryKeyMixin, TenantMixin, AuditMixin

INVITATION_STATUSES = ("pending", "accepted", "expired", "cancelled")
INVITATION_TTL_DAYS = 7


class Invitation(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    __tablename__ = "invitations"

    email = db.Column(db.String(255), nullable=False)
    role_id = db.Column(UUID(as_uuid=True), db.ForeignKey("roles.id"), nullable=False)
    department = db.Column(db.String(128), nullable=True)
    job_title = db.Column(db.String(128), nullable=True)
    invited_by_user_id = db.Column(UUID(as_uuid=True), nullable=True)
    message = db.Column(db.Text, nullable=True)

    # Never the raw token -- see app/org/services.py:hash_invitation_token
    # for the same reasoning already applied to password storage.
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    status = db.Column(db.String(16), nullable=False, default="pending")
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    accepted_at = db.Column(db.DateTime(timezone=True), nullable=True)

    role = db.relationship("Role")

    __table_args__ = (
        db.CheckConstraint(f"status IN {INVITATION_STATUSES}", name="ck_invitations_status"),
    )
