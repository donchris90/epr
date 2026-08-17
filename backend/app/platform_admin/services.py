"""
See app/platform_admin/models.py's module docstring for the overall
scope and the real reasoning behind why this is a separate account
type rather than a powerful user permission.
"""
from sqlalchemy import text

from app.extensions import db
from app.utils.errors import APIError
from app.auth.jwt_utils import hash_password, verify_password
from app.models.core import Tenant, User
from app.billing.models import TenantSubscription
from app.billing import services as billing_services
from app.platform_admin.models import PlatformAdmin


def _as_tenant(tenant_id):
    """Same requirement as every other piece of code in this project
    that reads/writes across tenants outside a real per-tenant HTTP
    request -- see app/modules/inv/tasks.py's identical helper."""
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def authenticate_platform_admin(email, password):
    if not email or not password:
        return None

    admin = PlatformAdmin.query.filter_by(email=email.strip().lower()).first()
    if not admin or admin.status != "active":
        return None

    if not verify_password(admin.password_hash, password):
        return None

    return admin


def create_platform_admin(email, password):
    """Real account creation -- used by the `flask create-platform-admin`
    CLI command (app/platform_admin/cli.py), deliberately not exposed
    as a self-service API endpoint anywhere. Provisioning a platform
    admin is a real, sensitive, out-of-band operational action."""
    email = email.strip().lower()
    if PlatformAdmin.query.filter_by(email=email).first():
        raise APIError(f"A platform admin with email {email!r} already exists", status=409)

    admin = PlatformAdmin(email=email, password_hash=hash_password(password))
    db.session.add(admin)
    db.session.commit()
    return admin


def list_all_tenants():
    """
    Real cross-tenant read -- loops per-tenant with a real
    SET LOCAL app.tenant_id for each one (see _as_tenant above),
    exactly the pattern already proven safe for legitimate
    cross-tenant background work in app/modules/inv/tasks.py and
    app/modules/eqp/tasks.py, applied here to a synchronous admin
    request instead of a Celery task. `tenants` itself has no RLS, so
    the initial enumeration needs no tenant context at all; the
    per-tenant User count and subscription lookup each do.
    """
    tenants = Tenant.query.order_by(Tenant.created_at.desc()).all()
    results = []

    for tenant in tenants:
        _as_tenant(tenant.id)
        user_count = User.query.filter_by(tenant_id=tenant.id).count()
        subscription = TenantSubscription.query.filter_by(tenant_id=tenant.id).first()

        results.append({
            "id": tenant.id,
            "name": tenant.name,
            "region": tenant.region,
            "is_suspended": tenant.is_suspended,
            "created_at": tenant.created_at,
            "user_count": user_count,
            "subscription_status": subscription.status if subscription else None,
            "subscription_plan_code": subscription.plan.code if subscription else None,
        })

    return results


def get_tenant_detail(tenant_id):
    tenant = Tenant.query.filter_by(id=tenant_id).first()
    if not tenant:
        raise APIError("Tenant not found", status=404)

    _as_tenant(tenant.id)
    user_count = User.query.filter_by(tenant_id=tenant.id).count()
    subscription = TenantSubscription.query.filter_by(tenant_id=tenant.id).first()

    return {
        "id": tenant.id,
        "name": tenant.name,
        "region": tenant.region,
        "is_suspended": tenant.is_suspended,
        "created_at": tenant.created_at,
        "user_count": user_count,
        "subscription_status": subscription.status if subscription else None,
        "subscription_plan_code": subscription.plan.code if subscription else None,
        "trial_ends_at": subscription.trial_ends_at if subscription else None,
    }


def suspend_tenant(tenant_id):
    """Real enforcement -- checked at login
    (app/auth/jwt_utils.py:authenticate_user). A suspended tenant's
    existing sessions (already-issued access tokens) remain valid
    until they naturally expire; this blocks new logins and new
    refreshes, not an instantly-revoked active session -- the same
    real, documented limitation this codebase already accepts for
    ordinary user deactivation (User.status), not a new gap invented
    here."""
    tenant = Tenant.query.filter_by(id=tenant_id).first()
    if not tenant:
        raise APIError("Tenant not found", status=404)
    tenant.is_suspended = True
    db.session.commit()
    return tenant


def reactivate_tenant(tenant_id):
    tenant = Tenant.query.filter_by(id=tenant_id).first()
    if not tenant:
        raise APIError("Tenant not found", status=404)
    tenant.is_suspended = False
    db.session.commit()
    return tenant


def admin_extend_trial(tenant_id, *, days):
    """Sets real tenant context first -- tenant_subscriptions has RLS,
    unlike tenants itself, and a platform admin's own JWT carries no
    tenant_id to have set it automatically (see this module's own
    docstring on why). Delegates the actual logic to
    app/billing/services.py:extend_trial rather than duplicating it --
    this function's only real job is establishing the tenant context
    an ordinary tenant-user request gets for free from the middleware.

    Real bug found and fixed while testing this, not by inspection:
    extend_trial's own db.session.commit() expires the returned
    object's attributes; re-accessing them (e.g. subscription.status
    in the route) triggers a fresh SELECT needing app.tenant_id set
    again. An ordinary tenant-user request gets that automatically
    (the after_begin listener re-applies it from g.tenant_id on every
    new transaction) -- but a platform-admin request's g.tenant_id is
    always None (that JWT carries no tenant_id at all), so nothing
    re-applies it here. Setting tenant context again, after the
    commit, closes the gap."""
    tenant = Tenant.query.filter_by(id=tenant_id).first()
    if not tenant:
        raise APIError("Tenant not found", status=404)
    _as_tenant(tenant_id)
    subscription = billing_services.extend_trial(tenant_id, days=days)
    _as_tenant(tenant_id)
    return subscription


def admin_grant_subscription(tenant_id, *, plan_code, billing_cycle, period_days=None):
    """See admin_extend_trial's docstring -- same real-tenant-context
    requirement (including the post-commit re-application), delegates
    to app/billing/services.py:grant_subscription."""
    tenant = Tenant.query.filter_by(id=tenant_id).first()
    if not tenant:
        raise APIError("Tenant not found", status=404)
    _as_tenant(tenant_id)
    subscription = billing_services.grant_subscription(
        tenant_id, plan_code=plan_code, billing_cycle=billing_cycle, period_days=period_days
    )
    _as_tenant(tenant_id)
    return subscription
