"""
Tests for real Paystack payment integration
(app/billing/services.py:initiate_paystack_checkout,
verify_paystack_webhook_signature, apply_paystack_webhook_event), the
real 402 subscription-enforcement middleware, and the admin
extend-trial/grant-subscription actions.
"""
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy import text


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def _set_subscription(db, tenant_id, plan, **fields):
    """seed_tenants (conftest.py) already grants every test tenant a
    real active subscription -- one row per tenant is a real DB
    constraint (uq_tenant_subscriptions_one_per_tenant), so a test
    that needs a different state (trialing, expired, etc.) updates
    that existing row rather than inserting a second, conflicting
    one."""
    from app.billing.models import TenantSubscription

    _as_tenant(db, tenant_id)
    subscription = TenantSubscription.query.filter_by(tenant_id=tenant_id).first()
    subscription.plan_id = plan.id
    for key, value in fields.items():
        setattr(subscription, key, value)
    db.session.commit()
    return subscription


def _seed_plan(db, code="starter", monthly=25000, annual=250000):
    from app.billing.models import SubscriptionPlan

    plan = SubscriptionPlan.query.filter_by(code=code).first()
    if plan:
        return plan
    plan = SubscriptionPlan(code=code, name=code.title(), monthly_price_ngn=monthly, annual_price_ngn=annual, seat_limit=5)
    db.session.add(plan)
    db.session.commit()
    return plan


class TestWebhookSignatureVerification:
    def test_correct_signature_verifies(self, app):
        app.config["PAYSTACK_SECRET_KEY"] = "sk_test_secret"
        with app.app_context():
            from app.billing.services import verify_paystack_webhook_signature

            body = b'{"event": "charge.success"}'
            sig = hmac.new(b"sk_test_secret", body, hashlib.sha512).hexdigest()
            assert verify_paystack_webhook_signature(body, sig) is True

    def test_tampered_body_is_rejected(self, app):
        app.config["PAYSTACK_SECRET_KEY"] = "sk_test_secret"
        with app.app_context():
            from app.billing.services import verify_paystack_webhook_signature

            original = b'{"event": "charge.success"}'
            sig = hmac.new(b"sk_test_secret", original, hashlib.sha512).hexdigest()
            tampered = b'{"event": "charge.success", "extra": "field"}'
            assert verify_paystack_webhook_signature(tampered, sig) is False

    def test_wrong_secret_is_rejected(self, app):
        app.config["PAYSTACK_SECRET_KEY"] = "sk_test_secret"
        with app.app_context():
            from app.billing.services import verify_paystack_webhook_signature

            body = b'{"event": "charge.success"}'
            sig = hmac.new(b"wrong_secret", body, hashlib.sha512).hexdigest()
            assert verify_paystack_webhook_signature(body, sig) is False

    def test_missing_signature_is_rejected(self, app):
        app.config["PAYSTACK_SECRET_KEY"] = "sk_test_secret"
        with app.app_context():
            from app.billing.services import verify_paystack_webhook_signature

            assert verify_paystack_webhook_signature(b"{}", None) is False

    def test_unconfigured_secret_rejects_everything(self, app):
        app.config["PAYSTACK_SECRET_KEY"] = ""
        with app.app_context():
            from app.billing.services import verify_paystack_webhook_signature

            body = b'{"event": "charge.success"}'
            sig = hmac.new(b"anything", body, hashlib.sha512).hexdigest()
            assert verify_paystack_webhook_signature(body, sig) is False


class TestInitiateCheckout:
    def test_constructs_the_real_paystack_request_correctly(self, app, db):
        app.config["PAYSTACK_SECRET_KEY"] = "sk_test_secret"
        _seed_plan(db)
        tenant_id = str(uuid.uuid4())

        mock_response = MagicMock()
        mock_response.raise_for_status = lambda: None
        mock_response.json.return_value = {
            "status": True,
            "data": {"authorization_url": "https://checkout.paystack.com/xyz", "access_code": "xyz", "reference": "ignored"},
        }

        with app.app_context():
            with patch("app.billing.services.requests.post", return_value=mock_response) as mock_post:
                from app.billing.services import initiate_paystack_checkout

                result = initiate_paystack_checkout(tenant_id, plan_code="starter", billing_cycle="monthly", email="a@b.com")

                assert result["authorization_url"] == "https://checkout.paystack.com/xyz"
                kwargs = mock_post.call_args.kwargs
                assert kwargs["json"]["amount"] == 2500000  # 25000 NGN in kobo
                assert kwargs["json"]["email"] == "a@b.com"
                assert kwargs["json"]["metadata"]["tenant_id"] == tenant_id
                assert kwargs["json"]["metadata"]["plan_code"] == "starter"

    def test_unconfigured_secret_key_returns_honest_501(self, app, db):
        app.config["PAYSTACK_SECRET_KEY"] = ""
        _seed_plan(db)
        with app.app_context():
            from app.billing.services import initiate_paystack_checkout
            from app.utils.errors import APIError
            import pytest

            with pytest.raises(APIError) as exc_info:
                initiate_paystack_checkout(str(uuid.uuid4()), plan_code="starter", billing_cycle="monthly", email="a@b.com")
            assert exc_info.value.status == 501


class TestWebhookRoute:
    def test_real_signed_webhook_activates_the_subscription(self, app, db, client, seed_tenants):
        app.config["PAYSTACK_SECRET_KEY"] = "sk_test_secret"
        plan = _seed_plan(db)
        _set_subscription(db, seed_tenants["a"], plan, status="trialing")

        payload = {
            "event": "charge.success",
            "data": {
                "reference": "sf-realtest",
                "amount": 2500000,
                "customer": {"customer_code": "CUS_test123"},
                "metadata": {"tenant_id": str(seed_tenants["a"]), "plan_code": "starter", "billing_cycle": "monthly"},
            },
        }
        raw_body = json.dumps(payload).encode()
        signature = hmac.new(b"sk_test_secret", raw_body, hashlib.sha512).hexdigest()

        r = client.post(
            "/v1/billing/paystack/webhook", data=raw_body,
            headers={"x-paystack-signature": signature, "Content-Type": "application/json"},
        )
        assert r.status_code == 200

        _as_tenant(db, seed_tenants["a"])
        from app.billing.models import TenantSubscription

        subscription = TenantSubscription.query.filter_by(tenant_id=seed_tenants["a"]).first()
        assert subscription.status == "active"
        assert subscription.paystack_customer_code == "CUS_test123"

    def test_unsigned_webhook_is_rejected(self, app, db, client):
        app.config["PAYSTACK_SECRET_KEY"] = "sk_test_secret"
        r = client.post(
            "/v1/billing/paystack/webhook", data=b'{"event": "charge.success"}',
            headers={"x-paystack-signature": "fake", "Content-Type": "application/json"},
        )
        assert r.status_code == 401

    def test_unrecognized_event_types_are_acknowledged_not_errored(self, app, db, client):
        app.config["PAYSTACK_SECRET_KEY"] = "sk_test_secret"
        raw_body = json.dumps({"event": "subscription.disable", "data": {}}).encode()
        signature = hmac.new(b"sk_test_secret", raw_body, hashlib.sha512).hexdigest()
        r = client.post(
            "/v1/billing/paystack/webhook", data=raw_body,
            headers={"x-paystack-signature": signature, "Content-Type": "application/json"},
        )
        assert r.status_code == 200


class TestSubscriptionEnforcementMiddleware:
    def test_expired_trial_blocks_ordinary_routes_with_402(self, app, db, client, seed_tenants, auth_headers):
        plan = _seed_plan(db)
        _set_subscription(db, seed_tenants["a"], plan, status="trialing", trial_ends_at=datetime.now(timezone.utc) - timedelta(days=1))

        headers = auth_headers("a", permissions=["*"])
        r = client.get("/v1/bdc/clients", headers=headers)
        assert r.status_code == 402

    def test_billing_routes_stay_reachable_even_when_inactive(self, app, db, client, seed_tenants, auth_headers):
        plan = _seed_plan(db)
        _set_subscription(db, seed_tenants["a"], plan, status="trialing", trial_ends_at=datetime.now(timezone.utc) - timedelta(days=1))

        headers = auth_headers("a", permissions=["billing:read"])
        r = client.get("/v1/billing/plans", headers=headers)
        assert r.status_code == 200
        r2 = client.get("/v1/billing/subscription", headers=headers)
        assert r2.status_code == 200
        assert r2.get_json()["is_active"] is False

    def test_active_trial_is_not_blocked(self, app, db, client, seed_tenants, auth_headers):
        plan = _seed_plan(db)
        _set_subscription(db, seed_tenants["a"], plan, status="trialing", trial_ends_at=datetime.now(timezone.utc) + timedelta(days=5))

        headers = auth_headers("a", permissions=["bdc:read"])
        r = client.get("/v1/bdc/clients", headers=headers)
        assert r.status_code == 200


class TestAdminExtendAndGrant:
    def test_extend_trial_pushes_the_date_forward(self, app, db, client, seed_tenants):
        from app.platform_admin.services import create_platform_admin

        create_platform_admin("extendtest@example.com", "adminpass123")
        plan = _seed_plan(db)
        original_end = datetime.now(timezone.utc) + timedelta(days=2)
        _set_subscription(db, seed_tenants["a"], plan, status="trialing", trial_ends_at=original_end)

        c = app.test_client()
        r = c.post("/v1/platform-admin/auth/login", json={"email": "extendtest@example.com", "password": "adminpass123"})
        admin_headers = {"Authorization": f"Bearer {r.get_json()['access_token']}"}

        r2 = c.post(f"/v1/platform-admin/tenants/{seed_tenants['a']}/extend-trial", headers=admin_headers, json={"days": 30})
        assert r2.status_code == 200
        new_end = datetime.fromisoformat(r2.get_json()["trial_ends_at"])
        assert new_end > original_end

    def test_grant_subscription_activates_with_no_payment(self, app, db, client, seed_tenants):
        from app.platform_admin.services import create_platform_admin

        create_platform_admin("granttest@example.com", "adminpass123")
        plan = _seed_plan(db)
        _set_subscription(db, seed_tenants["a"], plan, status="trialing")

        c = app.test_client()
        r = c.post("/v1/platform-admin/auth/login", json={"email": "granttest@example.com", "password": "adminpass123"})
        admin_headers = {"Authorization": f"Bearer {r.get_json()['access_token']}"}

        r2 = c.post(
            f"/v1/platform-admin/tenants/{seed_tenants['a']}/grant-subscription", headers=admin_headers,
            json={"plan_code": "starter", "billing_cycle": "annual", "period_days": 365},
        )
        assert r2.status_code == 200
        assert r2.get_json()["status"] == "active"

        _as_tenant(db, seed_tenants["a"])
        from app.billing.services import is_tenant_active

        assert is_tenant_active(seed_tenants["a"]) is True

    def test_grant_subscription_with_no_period_days_never_expires(self, app, db, client, seed_tenants):
        from app.platform_admin.services import create_platform_admin

        create_platform_admin("granttest2@example.com", "adminpass123")
        plan = _seed_plan(db)
        _set_subscription(db, seed_tenants["a"], plan, status="trialing")

        c = app.test_client()
        r = c.post("/v1/platform-admin/auth/login", json={"email": "granttest2@example.com", "password": "adminpass123"})
        admin_headers = {"Authorization": f"Bearer {r.get_json()['access_token']}"}

        r2 = c.post(
            f"/v1/platform-admin/tenants/{seed_tenants['a']}/grant-subscription", headers=admin_headers,
            json={"plan_code": "starter", "billing_cycle": "monthly"},
        )
        assert r2.status_code == 200
        assert r2.get_json()["current_period_end"] is None
