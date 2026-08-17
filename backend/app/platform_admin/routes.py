"""
Platform administration. Base path: /v1/platform-admin

See app/platform_admin/models.py's module docstring for the full
scope. The login route issues a real, distinct token type: no
tenant_id claim at all, and a real is_platform_admin claim that
require_platform_admin (app/utils/decorators.py) checks -- a platform
admin token is structurally incapable of passing an ordinary
require_permission check (it carries no permissions claim), and an
ordinary tenant-user token is structurally incapable of passing
require_platform_admin (it carries no is_platform_admin claim). Two
genuinely separate credential types, not one permission bit.
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token

from app.platform_admin import services
from app.platform_admin.schemas import TenantOverviewSchema, TenantDetailSchema
from app.utils.decorators import require_platform_admin
from app.utils.errors import APIError
from app.utils.pagination import envelope

bp = Blueprint("platform_admin", __name__, url_prefix="/v1/platform-admin")

tenant_overview_schema = TenantOverviewSchema()
tenant_detail_schema = TenantDetailSchema()


@bp.post("/auth/login")
def login():
    data = request.get_json(force=True) or {}
    admin = services.authenticate_platform_admin(data.get("email"), data.get("password"))
    if not admin:
        raise APIError("Invalid credentials", status=401)

    claims = {"is_platform_admin": True, "platform_admin_id": str(admin.id)}
    access_token = create_access_token(identity=str(admin.id), additional_claims=claims)
    return jsonify({"access_token": access_token})


@bp.get("/tenants")
@require_platform_admin
def list_tenants():
    tenants = services.list_all_tenants()
    return jsonify(envelope(tenant_overview_schema.dump(tenants, many=True)))


@bp.get("/tenants/<uuid:tenant_id>")
@require_platform_admin
def get_tenant(tenant_id):
    detail = services.get_tenant_detail(tenant_id)
    return jsonify(tenant_detail_schema.dump(detail))


@bp.post("/tenants/<uuid:tenant_id>/suspend")
@require_platform_admin
def suspend_tenant(tenant_id):
    tenant = services.suspend_tenant(tenant_id)
    return jsonify({"id": str(tenant.id), "is_suspended": tenant.is_suspended})


@bp.post("/tenants/<uuid:tenant_id>/reactivate")
@require_platform_admin
def reactivate_tenant(tenant_id):
    tenant = services.reactivate_tenant(tenant_id)
    return jsonify({"id": str(tenant.id), "is_suspended": tenant.is_suspended})


@bp.post("/tenants/<uuid:tenant_id>/extend-trial")
@require_platform_admin
def extend_trial(tenant_id):
    data = request.get_json(force=True) or {}
    days = data.get("days")
    if not isinstance(days, int) or days <= 0:
        raise APIError("days must be a positive integer", status=400)

    subscription = services.admin_extend_trial(tenant_id, days=days)
    return jsonify({
        "tenant_id": str(tenant_id),
        "status": subscription.status,
        "trial_ends_at": subscription.trial_ends_at.isoformat() if subscription.trial_ends_at else None,
    })


@bp.post("/tenants/<uuid:tenant_id>/grant-subscription")
@require_platform_admin
def grant_subscription(tenant_id):
    """Manually activates a tenant's subscription with no Paystack
    charge involved -- an offline payment, a comp account, or covering
    a provider outage. See app/billing/services.py:grant_subscription
    for the real reasoning behind period_days=None meaning "no expiry
    at all" versus a real fixed period."""
    data = request.get_json(force=True) or {}
    plan_code = data.get("plan_code")
    billing_cycle = data.get("billing_cycle", "monthly")
    period_days = data.get("period_days")

    if not plan_code:
        raise APIError("plan_code is required", status=400)
    if period_days is not None and (not isinstance(period_days, int) or period_days <= 0):
        raise APIError("period_days must be a positive integer or omitted", status=400)

    subscription = services.admin_grant_subscription(
        tenant_id, plan_code=plan_code, billing_cycle=billing_cycle, period_days=period_days
    )
    return jsonify({
        "tenant_id": str(tenant_id),
        "status": subscription.status,
        "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
    })
