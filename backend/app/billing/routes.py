"""
Subscription billing. Base path: /v1/billing

See app/billing/models.py's module docstring for full scope. Any
authenticated user can view plans/their own tenant's subscription
status (billing:read) -- changing the plan or paying is a tenant-
admin action (billing:manage), matching the same "reading is broader
than writing" pattern used across this codebase.
"""
from flask import Blueprint, g, jsonify, request

from app.billing import services
from app.billing.schemas import SubscriptionPlanSchema, TenantSubscriptionSchema, ChangePlanInputSchema
from app.extensions import db
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import envelope

bp = Blueprint("billing", __name__, url_prefix="/v1/billing")

plan_schema = SubscriptionPlanSchema()
subscription_schema = TenantSubscriptionSchema()


def _load(schema):
    data = request.get_json(force=True) or {}
    errors = schema.validate(data)
    if errors:
        raise APIError("Validation failed", status=400, detail=str(errors))
    return schema.load(data)


@bp.get("/plans")
@require_permission("billing:read")
def list_plans():
    return jsonify(envelope(plan_schema.dump(services.list_active_plans(), many=True)))


@bp.get("/subscription")
@require_permission("billing:read")
def get_subscription():
    subscription = services.get_subscription(g.tenant_id)
    if not subscription:
        raise APIError("No subscription found for this tenant", status=404)
    body = subscription_schema.dump(subscription)
    body["is_active"] = services.is_tenant_active(g.tenant_id)
    return jsonify(body)


@bp.post("/subscription/change-plan")
@require_permission("billing:manage")
def change_plan():
    data = _load(ChangePlanInputSchema())
    subscription = services.change_plan(g.tenant_id, plan_code=data["plan_code"], billing_cycle=data["billing_cycle"])
    db.session.commit()
    return jsonify(subscription_schema.dump(subscription))


@bp.post("/subscription/checkout")
@require_permission("billing:manage")
def initiate_checkout():
    """Real Paystack integration point -- see
    services.py:initiate_paystack_checkout for exactly what's needed
    to make this a real charge instead of a clear, honest 501."""
    data = _load(ChangePlanInputSchema())
    services.initiate_paystack_checkout(g.tenant_id, plan_code=data["plan_code"], billing_cycle=data["billing_cycle"])
