"""
Notifications -- in-app notifications, with email/SMS dispatch stubbed
behind a real extension point rather than faked.

Adapted from a real, working implementation found in a separate,
independent codebase generated against the same underlying SRS
(uploaded by the user as a reference/scaffold, not something to
discard -- see README.md's session notes on this). This platform had
zero notification infrastructure of any kind before this; every
module's audit trail recorded that something happened, but nothing
ever told anyone.

In-app notifications are always written (they back the notification
bell any frontend would build against this, and require no external
dependency). Email/SMS dispatch is deliberately stubbed, not faked --
see _dispatch_external below for exactly what's real and what isn't.
"""
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin


NOTIFICATION_CHANNELS = ("in_app", "email", "sms")


class Notification(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """One notification for one user. `type` is a dotted, machine-
    readable category (e.g. "workflow.approval_requested",
    "hse.incident_raised") -- lets a frontend route to the right icon
    or deep link without parsing free text out of `title`/`body`.
    `data` carries whatever a deep link needs (entity_type, entity_id,
    ...) as a real JSONB payload, not something a client has to
    reconstruct from the title string."""

    __tablename__ = "notifications"

    # Loose reference, not a hard FK -- matches the dominant convention
    # for user-identifier fields throughout this codebase
    # (WorkflowAction.actor_id, WorkflowInstance.initiated_by, and
    # nearly every other "who does this belong to" field), rather than
    # the one, inconsistent exception (app/models/core.py's Role.created_by
    # equivalent). A hard FK here would also mean every notification for
    # a deleted user needs explicit cascade handling; a loose reference
    # doesn't create that coupling.
    user_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    type = db.Column(db.String(64), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=True)
    data = db.Column(JSONB, nullable=True)
    channel = db.Column(db.String(16), nullable=False, default="in_app")
    read_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)

    __table_args__ = (
        db.CheckConstraint(f"channel IN {NOTIFICATION_CHANNELS}", name="ck_notifications_channel"),
        db.Index("ix_notifications_user_unread", "tenant_id", "user_id", "read_at"),
    )
