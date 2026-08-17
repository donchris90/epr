"""
Platform administration -- operating across every tenant, not within
one. Base path: /v1/platform-admin

Deliberately a completely separate account type from app.models.core.User,
not a special role/permission on an ordinary tenant user: a platform
admin needs to see and act across every tenant, which is fundamentally
incompatible with this codebase's whole RLS-based isolation model if
modeled as "just another user with a powerful permission." A real
platform-admin request instead loops per-tenant with a real
`SET LOCAL app.tenant_id` for each one it touches (see services.py) --
the exact same proven pattern already used for legitimate cross-tenant
background work in app/modules/inv/tasks.py and app/modules/eqp/tasks.py,
applied here to synchronous admin requests instead of a Celery task.

PlatformAdmin has no tenant_id and no RLS at all -- same reasoning as
Tenant itself: this is the root of the whole hierarchy, not scoped to
one node in it.
"""
from app.extensions import db
from app.models.base import UUIDPrimaryKeyMixin, AuditMixin

PLATFORM_ADMIN_STATUSES = ("active", "disabled")


class PlatformAdmin(db.Model, UUIDPrimaryKeyMixin, AuditMixin):
    __tablename__ = "platform_admins"

    email = db.Column(db.String(255), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(16), nullable=False, default="active")

    __table_args__ = (db.CheckConstraint(f"status IN {PLATFORM_ADMIN_STATUSES}", name="ck_platform_admins_status"),)
