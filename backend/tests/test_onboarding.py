"""
Tests for tenant self-service signup (app/onboarding/).

Regression coverage for a real bug found while building this: after
db.session.commit(), Flask-SQLAlchemy's default expire_on_commit=True
means the first touch of any ORM attribute triggers an implicit
re-SELECT -- and that SELECT runs in a brand new transaction with no
app.tenant_id GUC set, which FORCE ROW LEVEL SECURITY then rejects.
services.signup_tenant returns a plain dict of primitives captured
BEFORE commit specifically to avoid this; these tests would catch a
regression back to returning ORM objects directly.
"""
from app.models.core import Tenant, User


class TestSignup:
    def test_signup_creates_a_real_tenant_and_returns_working_tokens(self, client, db):
        r = client.post(
            "/v1/onboarding/signup",
            json={"company_name": "Test Signup Co", "admin_email": "founder@testsignup.com", "admin_password": "correct horse battery staple"},
        )
        assert r.status_code == 201
        body = r.get_json()
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["tenant_id"]

        # The auto-issued token must actually work on a real protected route.
        r2 = client.get("/v1/prc/vendors", headers={"Authorization": f"Bearer {body['access_token']}"})
        assert r2.status_code == 200

    def test_signup_requires_no_authorization_header_at_all(self, client, db):
        """The whole point -- unlike virtually every other route in
        this codebase, this one must work with zero prior auth state."""
        r = client.post(
            "/v1/onboarding/signup",
            json={"company_name": "No Auth Co", "admin_email": "noauth@example.com", "admin_password": "correct horse battery staple"},
        )
        assert r.status_code == 201

    def test_rejects_short_password(self, client, db):
        r = client.post(
            "/v1/onboarding/signup",
            json={"company_name": "Bad Co", "admin_email": "bad@example.com", "admin_password": "short"},
        )
        assert r.status_code == 400

    def test_rejects_invalid_email(self, client, db):
        r = client.post(
            "/v1/onboarding/signup",
            json={"company_name": "Bad Co", "admin_email": "not-an-email", "admin_password": "correct horse battery staple"},
        )
        assert r.status_code == 400

    def test_two_signups_are_fully_isolated_tenants(self, client, db):
        r1 = client.post(
            "/v1/onboarding/signup",
            json={"company_name": "Tenant One Co", "admin_email": "one@example.com", "admin_password": "correct horse battery staple"},
        )
        r2 = client.post(
            "/v1/onboarding/signup",
            json={"company_name": "Tenant Two Co", "admin_email": "two@example.com", "admin_password": "correct horse battery staple"},
        )
        token1 = r1.get_json()["access_token"]
        token2 = r2.get_json()["access_token"]

        client.post("/v1/prc/vendors", headers={"Authorization": f"Bearer {token2}"}, json={"name": "Tenant Two's Vendor"})

        r3 = client.get("/v1/prc/vendors", headers={"Authorization": f"Bearer {token1}"})
        names = [v["name"] for v in r3.get_json()["data"]]
        assert "Tenant Two's Vendor" not in names
