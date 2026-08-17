"""
See app/billing/models.py's module docstring for the overall scope
and what's deliberately not built (real payment charging).
"""
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.utils.errors import APIError
from app.billing.models import SubscriptionPlan, TenantSubscription

TRIAL_DAYS = 14
# The plan a new trial defaults to -- see migrations/versions/0038_billing_plans.py's
# own note on this being a real, adjustable business decision, not
# something buried where it's hard to find. "growth" (the middle
# tier) is a common SaaS default: let a new tenant experience the
# fuller product during the trial; they choose what to actually pay
# for once it ends, rather than being limited to the entry tier while
# evaluating.
DEFAULT_TRIAL_PLAN_CODE = "growth"


def list_active_plans():
    return SubscriptionPlan.query.filter_by(is_active=True).order_by(SubscriptionPlan.monthly_price_ngn).all()


def start_trial(tenant_id, *, plan_code=None):
    """
    Called once, from signup (app/onboarding/services.py) -- creates
    the tenant's one TenantSubscription row in "trialing" status,
    trial_ends_at 14 real days from now. Does not touch payment in
    any way; a trial needs no card on file to start.

    Deliberately tolerant of a missing plan catalog: signup creating a
    real tenant and a real login-capable user is the actual core
    transaction here; starting a trial is a real but secondary
    concern layered on top of it, the same principle already applied
    to notification delivery never being allowed to break the
    transaction that triggered it (app/notifications/services.py).
    In real production this can't happen -- migration 0038 always
    seeds the plan catalog -- but a genuinely misconfigured or
    not-yet-migrated environment should get a tenant that can log in
    with no subscription (is_tenant_active correctly fails closed for
    that case) rather than no tenant at all.
    """
    plan = SubscriptionPlan.query.filter_by(code=plan_code or DEFAULT_TRIAL_PLAN_CODE, is_active=True).first()
    if not plan:
        plan = SubscriptionPlan.query.filter_by(is_active=True).first()
    if not plan:
        return None

    now = datetime.now(timezone.utc)
    subscription = TenantSubscription(
        tenant_id=tenant_id,
        plan_id=plan.id,
        billing_cycle="monthly",
        status="trialing",
        trial_ends_at=now + timedelta(days=TRIAL_DAYS),
    )
    db.session.add(subscription)
    return subscription


def get_subscription(tenant_id):
    return TenantSubscription.query.filter_by(tenant_id=tenant_id).first()


def is_tenant_active(tenant_id) -> bool:
    """
    The real, single source of truth for "does this tenant currently
    have access" -- trialing (before trial_ends_at) or active both
    count; past_due/canceled/expired don't. A tenant with no
    subscription row at all (shouldn't happen after the 0038 backfill,
    but a real, honest edge case worth handling rather than crashing
    on) is treated as inactive -- fail closed, not open.

    Deliberately NOT wired into request-blocking middleware in this
    pass -- see README.md's session notes for why: enforcing this
    automatically is a real, separate, higher-stakes decision (risk of
    locking out a tenant that predates or falls outside this system's
    assumptions) left for deliberate, explicit follow-up rather than
    silently changing what every existing request does.
    """
    subscription = get_subscription(tenant_id)
    if not subscription:
        return False
    if subscription.status == "active":
        return True
    if subscription.status == "trialing":
        return subscription.trial_ends_at is not None and datetime.now(timezone.utc) < subscription.trial_ends_at
    return False


def change_plan(tenant_id, *, plan_code, billing_cycle):
    """
    Records the tenant's chosen plan/cycle -- does NOT charge
    anything or change `status`. A plan selection made while trialing
    stays "trialing" until a real payment actually lands (see
    initiate_paystack_checkout); this function alone cannot move a
    tenant to "active".
    """
    if billing_cycle not in ("monthly", "annual"):
        raise APIError("billing_cycle must be 'monthly' or 'annual'", status=400)

    plan = SubscriptionPlan.query.filter_by(code=plan_code, is_active=True).first()
    if not plan:
        raise APIError(f"No active plan found for code {plan_code!r}", status=404)

    subscription = get_subscription(tenant_id)
    if not subscription:
        raise APIError("Tenant has no subscription record", status=404)

    subscription.plan_id = plan.id
    subscription.billing_cycle = billing_cycle
    return subscription


def initiate_paystack_checkout(tenant_id, *, plan_code, billing_cycle):
    """
    The real integration point for actual payment collection --
    deliberately not implemented, stated plainly rather than faked
    with a hardcoded "success" response. Wiring this up for real needs:

      1. A real PAYSTACK_SECRET_KEY (see app/config.py -- follow the
         exact pattern SMTP_USERNAME/SMTP_PASSWORD already established:
         empty by default, a clean documented no-op until set, never a
         crash).
      2. A call to Paystack's Initialize Transaction API
         (https://api.paystack.co/transaction/initialize) with the
         plan's real price (monthly_price_ngn/annual_price_ngn * 100,
         Paystack takes kobo) and a callback_url.
      3. A real webhook endpoint (POST /v1/billing/paystack/webhook)
         verifying Paystack's x-paystack-signature header against the
         secret key, then -- and only then -- updating this
         subscription's status to "active", current_period_start/end,
         and paystack_customer_code/paystack_subscription_code. Never
         trust a client-side "payment succeeded" callback alone for
         this; the webhook, signature-verified, is the only real
         source of truth an actual payment happened.

    Raising rather than returning a fake success -- exactly the same
    honesty this codebase already applies to AI/SMS: a feature that
    looks like it works but doesn't is worse than one that says so.
    """
    raise APIError(
        "Payment processing is not yet connected",
        status=501,
        detail="PAYSTACK_SECRET_KEY is not configured. See app/billing/services.py:initiate_paystack_checkout for the exact integration this needs.",
    )
