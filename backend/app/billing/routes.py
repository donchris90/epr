"""
Subscription billing. Base path: /v1/billing

See app/billing/models.py's module docstring for full scope. Any
authenticated user can view plans/their own tenant's subscription
status (billing:read) -- changing the plan or paying is a tenant-
admin action (billing:manage), matching the same "reading is broader
than writing" pattern used across this codebase.

The webhook route is the one real exception to all of the above: no
require_permission, no tenant-scoped JWT at all (Paystack can't send
one) -- its entire security model is the signature check inside
services.py:verify_paystack_webhook_signature. It's also listed in
app/middleware/tenant_context.py's PUBLIC_PATHS, since the ordinary
before_request hook has no JWT to verify here either.
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
    """Real Paystack integration -- returns a real authorization_url
    the frontend redirects the browser to. See
    services.py:initiate_paystack_checkout for what actually marks a
    subscription paid (never this response alone -- the webhook
    below, signature-verified, is the real source of truth)."""
    data = _load(ChangePlanInputSchema())

    from app.models.core import User

    user = User.query.filter_by(id=g.user_id, tenant_id=g.tenant_id).first()
    if not user or not user.email:
        raise APIError("Could not determine an email address for checkout", status=400)

    result = services.initiate_paystack_checkout(
        g.tenant_id, plan_code=data["plan_code"], billing_cycle=data["billing_cycle"], email=user.email
    )
    return jsonify(result)


@bp.post("/paystack/webhook")
def paystack_webhook():
    """No auth decorator at all -- Paystack cannot send a JWT, and
    this endpoint's real security is the signature check below, not
    RBAC. Always returns 200 once the signature check passes, even for
    event types this doesn't handle -- see
    services.py:apply_paystack_webhook_event's own docstring on why a
    5xx here just trains Paystack's retry logic to keep hammering an
    endpoint that was never going to accept the event."""
    raw_body = request.get_data()
    signature = request.headers.get("x-paystack-signature")

    if not services.verify_paystack_webhook_signature(raw_body, signature):
        raise APIError("Invalid signature", status=401)

    services.apply_paystack_webhook_event(request.get_json(force=True) or {})
    return jsonify({"status": "ok"})
