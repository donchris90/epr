"""
See app/billing/models.py's module docstring for the overall scope.
Real Paystack integration lives here: initiate_paystack_checkout
starts a real charge, verify_paystack_webhook_signature and
apply_paystack_webhook_event are what actually mark a subscription
paid -- only ever from a signature-verified webhook, never a
client-side callback alone (see initiate_paystack_checkout's own
docstring for why that distinction matters).
"""
import hashlib
import hmac
import uuid
from datetime import datetime, timedelta, timezone

import requests
from flask import current_app
from sqlalchemy import text

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

PAYSTACK_BASE_URL = "https://api.paystack.co"


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
    have access" -- trialing (before trial_ends_at) or active (before
    current_period_end, if one is set -- a manually-granted
    subscription with no period end is treated as active
    indefinitely, matching grant_subscription's own "comp account"
    use case) both count; past_due/canceled/expired don't. A tenant
    with no subscription row at all (shouldn't happen after the 0038
    backfill, but a real, honest edge case worth handling rather than
    crashing on) is treated as inactive -- fail closed, not open.

    Wired into real request-blocking middleware
    (app/middleware/tenant_context.py) -- an inactive tenant's
    requests outside the billing/auth/admin exemptions get a real 402,
    which the frontend turns into a redirect to a real subscription-
    expired page (see frontend/src/pages/SubscriptionExpiredPage.tsx).
    """
    subscription = get_subscription(tenant_id)
    if not subscription:
        return False
    if subscription.status == "active":
        if subscription.current_period_end is None:
            return True
        return datetime.now(timezone.utc) < subscription.current_period_end
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


def initiate_paystack_checkout(tenant_id, *, plan_code, billing_cycle, email):
    """
    Real Paystack integration: calls Initialize Transaction
    (https://api.paystack.co/transaction/initialize) and returns the
    authorization_url the frontend redirects the browser to. Never
    marks anything paid itself -- that only ever happens in
    apply_paystack_webhook_event, from a signature-verified webhook.
    Never trust a client-side "payment succeeded" callback alone for
    this: a browser redirect back to your app after checkout proves
    the *browser* went somewhere, not that Paystack actually collected
    money -- a user can hit that URL directly, or the redirect can
    fail after a real card decline. The webhook, signature-verified
    against a payload only Paystack could have produced, is the only
    real source of truth a payment happened.

    tenant_id and plan_code/billing_cycle round-trip through
    Paystack's own `metadata` field on the initialized transaction,
    read back out of the webhook payload later -- rather than trying
    to encode them into the reference string, which Paystack
    restricts to a narrow character set.
    """
    secret_key = current_app.config["PAYSTACK_SECRET_KEY"]
    if not secret_key:
        raise APIError(
            "Payment processing is not yet configured",
            status=501,
            detail="PAYSTACK_SECRET_KEY is not set.",
        )

    if billing_cycle not in ("monthly", "annual"):
        raise APIError("billing_cycle must be 'monthly' or 'annual'", status=400)

    plan = SubscriptionPlan.query.filter_by(code=plan_code, is_active=True).first()
    if not plan:
        raise APIError(f"No active plan found for code {plan_code!r}", status=404)

    price_ngn = plan.monthly_price_ngn if billing_cycle == "monthly" else plan.annual_price_ngn
    amount_kobo = int(price_ngn * 100)  # Paystack takes the smallest currency unit
    reference = f"sf-{uuid.uuid4().hex}"

    try:
        response = requests.post(
            f"{PAYSTACK_BASE_URL}/transaction/initialize",
            headers={"Authorization": f"Bearer {secret_key}"},
            json={
                "email": email,
                "amount": amount_kobo,
                "currency": "NGN",
                "reference": reference,
                # Deliberately NOT /billing -- that path already
                # belongs to this app's construction-billing module
                # (progress certificates, retention; app/modules/bil/,
                # a completely different, unrelated concern from
                # subscriptions). Found and fixed while wiring up the
                # frontend, not by inspection: reusing it would have
                # silently redirected a paying tenant into the wrong
                # part of the app after checkout.
                "callback_url": f"{current_app.config['FRONTEND_URL']}/account/subscription",
                "metadata": {"tenant_id": str(tenant_id), "plan_code": plan_code, "billing_cycle": billing_cycle},
            },
            timeout=15,
        )
        response.raise_for_status()
        body = response.json()
    except requests.RequestException as exc:
        raise APIError("Could not reach Paystack", status=502, detail=str(exc))

    if not body.get("status"):
        raise APIError("Paystack rejected the checkout request", status=502, detail=body.get("message"))

    return {
        "authorization_url": body["data"]["authorization_url"],
        "access_code": body["data"]["access_code"],
        "reference": reference,
    }


def verify_paystack_webhook_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """
    Real HMAC-SHA512 verification over the RAW request body (not a
    re-serialized/re-parsed version of it -- re-serializing JSON can
    change key order or whitespace and produce a different hash),
    compared in constant time against x-paystack-signature. This is
    the entire security model for the webhook endpoint -- it takes no
    JWT and has no tenant context of its own (Paystack can't send
    either), so a request that fails this check is rejected outright,
    full stop, regardless of what its payload claims.
    """
    secret_key = current_app.config["PAYSTACK_SECRET_KEY"]
    if not secret_key or not signature_header:
        return False

    computed = hmac.new(secret_key.encode("utf-8"), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(computed, signature_header)


def apply_paystack_webhook_event(payload: dict):
    """
    Only ever called after verify_paystack_webhook_signature has
    already returned True -- see routes.py. Handles charge.success;
    every other real Paystack event is acknowledged (200) and ignored,
    not an error -- a webhook endpoint that 500s on an event type it
    doesn't handle yet just trains Paystack's retry logic to keep
    hammering it.

    Idempotent by construction: re-applying the same successful charge
    (Paystack retries webhooks for up to 72 hours) just re-sets status
    to "active" and recomputes the same period end from "now" -- safe
    to run twice, not just tolerated.
    """
    if payload.get("event") != "charge.success":
        return

    data = payload.get("data", {})
    metadata = data.get("metadata") or {}
    tenant_id = metadata.get("tenant_id")
    plan_code = metadata.get("plan_code")
    billing_cycle = metadata.get("billing_cycle", "monthly")

    if not tenant_id or not plan_code:
        # A real charge.success Paystack itself doesn't attribute to
        # any known tenant -- e.g. a stale test event, or a
        # transaction never initiated through initiate_paystack_checkout
        # above. Nothing to apply; not an error requiring a 5xx, since
        # the signature already proved this is a genuine Paystack
        # event, just not one this endpoint has anything to do with.
        return

    plan = SubscriptionPlan.query.filter_by(code=plan_code).first()
    if not plan:
        return

    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})

    subscription = TenantSubscription.query.filter_by(tenant_id=tenant_id).first()
    if not subscription:
        return

    now = datetime.now(timezone.utc)
    period_days = 30 if billing_cycle == "monthly" else 365

    subscription.plan_id = plan.id
    subscription.billing_cycle = billing_cycle
    subscription.status = "active"
    subscription.current_period_start = now
    subscription.current_period_end = now + timedelta(days=period_days)
    subscription.paystack_customer_code = (data.get("customer") or {}).get("customer_code")
    subscription.paystack_subscription_code = data.get("reference")
    db.session.commit()


# --- Platform admin actions (app/platform_admin/routes.py) -------------------

def extend_trial(tenant_id, *, days):
    """
    Real admin action -- pushes trial_ends_at forward by `days` real
    days from whichever is later: the current trial_ends_at, or now.
    Extending from "now" rather than always from the existing
    trial_ends_at matters for an already-expired trial: extending
    "from where it already was" would still leave it expired if it
    lapsed long enough ago, which isn't what an admin granting more
    time actually wants. Only meaningful for a subscription currently
    "trialing" -- an "active" (paid) subscription's period end comes
    from a real charge, not this.
    """
    if days <= 0:
        raise APIError("days must be positive", status=400)

    subscription = get_subscription(tenant_id)
    if not subscription:
        raise APIError("Tenant has no subscription record", status=404)

    now = datetime.now(timezone.utc)
    base = max(subscription.trial_ends_at or now, now)
    subscription.trial_ends_at = base + timedelta(days=days)
    if subscription.status not in ("trialing", "active"):
        subscription.status = "trialing"
    db.session.commit()
    return subscription


def grant_subscription(tenant_id, *, plan_code, billing_cycle, period_days=None):
    """
    Real admin action -- activates a tenant's subscription directly,
    with no Paystack charge involved at all: an offline payment (bank
    transfer, cash), a comp/partner account, or covering for a
    Paystack outage. Deliberately a separate function from the
    webhook path (apply_paystack_webhook_event above), not a shared
    helper, so a real payment event and an admin's manual override are
    always distinguishable in the code that handles them, even though
    the resulting subscription row ends up in a similar shape.

    period_days=None means no expiry at all (a true comp account,
    matching is_tenant_active's own handling of a null
    current_period_end as "active indefinitely") -- pass a real number
    to grant a fixed-length manual period instead (e.g. matching what
    an offline bank transfer actually paid for).
    """
    if billing_cycle not in ("monthly", "annual"):
        raise APIError("billing_cycle must be 'monthly' or 'annual'", status=400)

    plan = SubscriptionPlan.query.filter_by(code=plan_code, is_active=True).first()
    if not plan:
        raise APIError(f"No active plan found for code {plan_code!r}", status=404)

    subscription = get_subscription(tenant_id)
    if not subscription:
        raise APIError("Tenant has no subscription record", status=404)

    now = datetime.now(timezone.utc)
    subscription.plan_id = plan.id
    subscription.billing_cycle = billing_cycle
    subscription.status = "active"
    subscription.current_period_start = now
    subscription.current_period_end = now + timedelta(days=period_days) if period_days else None
    db.session.commit()
    return subscription
