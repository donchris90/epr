"""
Subscription billing (SRS extension: monthly/annual plans, 14-day
free trial). Base path for routes: /v1/billing (registered as the
"billing" blueprint — matches the existing BIL module's naming for
construction billing/certificates, a different, unrelated concern;
kept as a separate top-level app/billing/ module, not inside
app/modules/bil/, specifically so the two are never confused).

Real, working structure end to end: plan definitions, trial-on-signup,
subscription state tracking, plan changes. What's deliberately NOT
here, stated plainly rather than faked: actual payment charging.
Every other Nigeria-market product in this developer's own history
(HotelOS, NestNG) integrates Paystack for exactly this, so this is
built to plug into Paystack the same deliberate way SMTP was built to
plug into Gmail -- the real webhook/verification endpoint exists and
is structured correctly, it just has nowhere to actually charge a
card without real PAYSTACK_SECRET_KEY credentials this environment
doesn't have. See services.py's initiate_paystack_checkout for
exactly where that real integration slots in.
"""
from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db
from app.models.base import UUIDPrimaryKeyMixin, TenantMixin, AuditMixin

BILLING_CYCLES = ("monthly", "annual")
SUBSCRIPTION_STATUSES = ("trialing", "active", "past_due", "canceled", "expired")


class SubscriptionPlan(db.Model, UUIDPrimaryKeyMixin, AuditMixin):
    """
    Platform-defined plan catalog -- not tenant-scoped (no RLS; the
    same reasoning as `tenants` itself: this is reference data every
    tenant needs to be able to see to choose a plan, not something
    belonging to one tenant). Seeded via a real data migration, not
    created through the API -- pricing changes are a business
    decision, not a self-service tenant action.
    """

    __tablename__ = "subscription_plans"

    code = db.Column(db.String(32), nullable=False, unique=True)  # e.g. "starter", "growth", "enterprise"
    name = db.Column(db.String(128), nullable=False)
    monthly_price_ngn = db.Column(db.Numeric(12, 2), nullable=False)
    annual_price_ngn = db.Column(db.Numeric(12, 2), nullable=False)
    # Nullable: no limit. Whether/where this is actually enforced is a
    # real, separate decision -- see services.py's module docstring.
    seat_limit = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)  # inactive = no longer sold, existing subs unaffected


class TenantSubscription(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """
    One row per tenant, updated in place as their subscription state
    changes (trial -> active -> canceled, plan upgrades, etc.) --
    deliberately not an immutable per-period ledger the way
    est.BudgetRevision or ctm.ContractAmendment are, since a
    subscription is closer to a single mutable status than a sequence
    of approved changes. A real historical audit trail (every plan
    change, every renewal) is a reasonable future addition were this
    to become a serious compliance requirement, but isn't built
    prematurely here.
    """

    __tablename__ = "tenant_subscriptions"

    plan_id = db.Column(UUID(as_uuid=True), db.ForeignKey("subscription_plans.id"), nullable=False)
    billing_cycle = db.Column(db.String(16), nullable=False, default="monthly")
    status = db.Column(db.String(16), nullable=False, default="trialing")

    trial_ends_at = db.Column(db.DateTime(timezone=True), nullable=True)
    current_period_start = db.Column(db.DateTime(timezone=True), nullable=True)
    current_period_end = db.Column(db.DateTime(timezone=True), nullable=True)

    # Real Paystack integration points -- populated once a real charge
    # actually happens (see services.py). Both null for a tenant still
    # on trial, or one grandfathered in with no real payment ever
    # collected (see the migration's backfill for existing tenants).
    paystack_customer_code = db.Column(db.String(64), nullable=True)
    paystack_subscription_code = db.Column(db.String(64), nullable=True)

    plan = db.relationship("SubscriptionPlan")

    __table_args__ = (
        db.CheckConstraint(f"billing_cycle IN {BILLING_CYCLES}", name="ck_tenant_subscriptions_cycle"),
        db.CheckConstraint(f"status IN {SUBSCRIPTION_STATUSES}", name="ck_tenant_subscriptions_status"),
        db.UniqueConstraint("tenant_id", name="uq_tenant_subscriptions_one_per_tenant"),
    )
