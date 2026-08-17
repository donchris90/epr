"""
Tests for app/billing/ -- real subscription plans, 14-day trial on
signup, plan changes, and an honest (not faked) payment-checkout
failure until real Paystack credentials exist.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import text


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def _seed_plans(db):
    """Tests use db.create_all() (schema from SQLAlchemy metadata
    alone -- see conftest.py), not the real Alembic migrations, so
    migration 0038's seeded plan rows are never present here. Mirrors
    that seed data exactly (same codes/prices) rather than inventing
    different test fixtures the real migration doesn't match."""
    from app.billing.models import SubscriptionPlan

    plans = [
        SubscriptionPlan(code="starter", name="Starter", monthly_price_ngn=25000, annual_price_ngn=250000, seat_limit=5),
        SubscriptionPlan(code="growth", name="Growth", monthly_price_ngn=75000, annual_price_ngn=750000, seat_limit=20),
        SubscriptionPlan(code="enterprise", name="Enterprise", monthly_price_ngn=200000, annual_price_ngn=2000000, seat_limit=None),
    ]
    db.session.add_all(plans)
    db.session.commit()


class TestSignupStartsARealTrial:
    def test_signup_creates_a_trialing_subscription_on_the_default_plan(self, app, db, client):
        _seed_plans(db)

        r = client.post("/v1/onboarding/signup", json={
            "company_name": "Trial Test Co", "admin_email": "trialtest@example.com", "admin_password": "testpassword123",
        })
        assert r.status_code == 201
        tenant_id = r.get_json()["tenant_id"]

        _as_tenant(db, tenant_id)
        from app.billing.models import TenantSubscription
        subscription = TenantSubscription.query.filter_by(tenant_id=tenant_id).first()

        assert subscription is not None
        assert subscription.status == "trialing"
        assert subscription.plan.code == "growth"

        now = datetime.now(timezone.utc)
        assert subscription.trial_ends_at > now + timedelta(days=13)
        assert subscription.trial_ends_at < now + timedelta(days=15)

    def test_signup_still_succeeds_with_no_plan_catalog_at_all(self, app, db, client):
        """The real regression this guards: signup creating a tenant
        and a login-capable user is the core transaction -- a missing
        or misconfigured plan catalog (no _seed_plans call here, on
        purpose) must never be the reason a new company can't sign up."""
        r = client.post("/v1/onboarding/signup", json={
            "company_name": "No Plans Co", "admin_email": "noplans@example.com", "admin_password": "testpassword123",
        })
        assert r.status_code == 201
        assert "access_token" in r.get_json()

        tenant_id = r.get_json()["tenant_id"]
        _as_tenant(db, tenant_id)
        from app.billing.models import TenantSubscription
        assert TenantSubscription.query.filter_by(tenant_id=tenant_id).first() is None


class TestIsTenantActive:
    def test_trialing_before_expiry_is_active(self, app, db, seed_tenants):
        _seed_plans(db)
        from app.billing.services import is_tenant_active
        from app.billing.models import SubscriptionPlan, TenantSubscription

        _as_tenant(db, seed_tenants["a"])
        plan = SubscriptionPlan.query.filter_by(code="starter").first()
        sub = TenantSubscription(
            tenant_id=seed_tenants["a"], plan_id=plan.id, status="trialing",
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=5),
        )
        db.session.add(sub)
        db.session.commit()

        _as_tenant(db, seed_tenants["a"])
        assert is_tenant_active(seed_tenants["a"]) is True

    def test_trialing_after_expiry_is_not_active(self, app, db, seed_tenants):
        _seed_plans(db)
        from app.billing.services import is_tenant_active
        from app.billing.models import SubscriptionPlan, TenantSubscription

        _as_tenant(db, seed_tenants["a"])
        plan = SubscriptionPlan.query.filter_by(code="starter").first()
        sub = TenantSubscription(
            tenant_id=seed_tenants["a"], plan_id=plan.id, status="trialing",
            trial_ends_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db.session.add(sub)
        db.session.commit()

        _as_tenant(db, seed_tenants["a"])
        assert is_tenant_active(seed_tenants["a"]) is False

    def test_active_status_is_active_regardless_of_trial_end(self, app, db, seed_tenants):
        _seed_plans(db)
        from app.billing.services import is_tenant_active
        from app.billing.models import SubscriptionPlan, TenantSubscription

        _as_tenant(db, seed_tenants["a"])
        plan = SubscriptionPlan.query.filter_by(code="starter").first()
        sub = TenantSubscription(tenant_id=seed_tenants["a"], plan_id=plan.id, status="active", trial_ends_at=None)
        db.session.add(sub)
        db.session.commit()

        _as_tenant(db, seed_tenants["a"])
        assert is_tenant_active(seed_tenants["a"]) is True

    def test_canceled_is_not_active(self, app, db, seed_tenants):
        _seed_plans(db)
        from app.billing.services import is_tenant_active
        from app.billing.models import SubscriptionPlan, TenantSubscription

        _as_tenant(db, seed_tenants["a"])
        plan = SubscriptionPlan.query.filter_by(code="starter").first()
        sub = TenantSubscription(tenant_id=seed_tenants["a"], plan_id=plan.id, status="canceled")
        db.session.add(sub)
        db.session.commit()

        _as_tenant(db, seed_tenants["a"])
        assert is_tenant_active(seed_tenants["a"]) is False

    def test_no_subscription_row_at_all_fails_closed(self, app, db, seed_tenants):
        from app.billing.services import is_tenant_active

        _as_tenant(db, seed_tenants["a"])
        assert is_tenant_active(seed_tenants["a"]) is False


class TestBillingRoutes:
    def test_list_plans_returns_the_real_seeded_plans(self, app, db, client, seed_tenants, auth_headers):
        _seed_plans(db)
        headers = auth_headers("a", permissions=["billing:read"])
        r = client.get("/v1/billing/plans", headers=headers)
        assert r.status_code == 200
        codes = {p["code"] for p in r.get_json()["data"]}
        assert codes == {"starter", "growth", "enterprise"}

    def test_get_subscription_reports_is_active_correctly(self, app, db, client, seed_tenants, auth_headers):
        _seed_plans(db)
        from app.billing.models import SubscriptionPlan, TenantSubscription

        _as_tenant(db, seed_tenants["a"])
        plan = SubscriptionPlan.query.filter_by(code="starter").first()
        db.session.add(TenantSubscription(tenant_id=seed_tenants["a"], plan_id=plan.id, status="active"))
        db.session.commit()

        headers = auth_headers("a", permissions=["billing:read"])
        r = client.get("/v1/billing/subscription", headers=headers)
        assert r.status_code == 200
        assert r.get_json()["is_active"] is True
        assert r.get_json()["plan"]["code"] == "starter"

    def test_change_plan_updates_plan_without_activating(self, app, db, client, seed_tenants, auth_headers):
        _seed_plans(db)
        from app.billing.models import SubscriptionPlan, TenantSubscription

        _as_tenant(db, seed_tenants["a"])
        plan = SubscriptionPlan.query.filter_by(code="growth").first()
        db.session.add(TenantSubscription(tenant_id=seed_tenants["a"], plan_id=plan.id, status="trialing"))
        db.session.commit()

        headers = auth_headers("a", permissions=["billing:manage"])
        r = client.post("/v1/billing/subscription/change-plan", headers=headers, json={"plan_code": "enterprise", "billing_cycle": "annual"})
        assert r.status_code == 200
        assert r.get_json()["plan"]["code"] == "enterprise"
        assert r.get_json()["billing_cycle"] == "annual"
        assert r.get_json()["status"] == "trialing"  # unchanged -- a plan pick alone never activates

    def test_checkout_honestly_fails_rather_than_faking_success(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["billing:manage"])
        r = client.post("/v1/billing/subscription/checkout", headers=headers, json={"plan_code": "starter", "billing_cycle": "monthly"})
        assert r.status_code == 501

    def test_cross_tenant_isolation(self, app, db, client, seed_tenants, auth_headers):
        _seed_plans(db)
        from app.billing.models import SubscriptionPlan, TenantSubscription

        _as_tenant(db, seed_tenants["a"])
        plan = SubscriptionPlan.query.filter_by(code="starter").first()
        db.session.add(TenantSubscription(tenant_id=seed_tenants["a"], plan_id=plan.id, status="active"))
        db.session.commit()

        headers_b = auth_headers("b", permissions=["billing:read"])
        r = client.get("/v1/billing/subscription", headers=headers_b)
        assert r.status_code == 404  # tenant B genuinely has no subscription of its own here
