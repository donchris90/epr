"""
Regression coverage for a real production outage: login was
completely broken on every real deployment, because the pre-tenant
email lookup (app/auth/jwt_utils.py:authenticate_user) depended on a
BYPASSRLS Postgres role that turned out to be impossible to provision
from application code -- Postgres requires the granting role to
itself have BYPASSRLS to hand that attribute to anyone else, which the
hosting provider's own database role didn't have. Confirmed directly
against the real production traceback before concluding this and
replacing the mechanism entirely with EmailTenantIndex (see
app/models/core.py for the full design reasoning).

These tests deliberately never grant any special role or set
AUTH_DATABASE_URL -- the whole point is that the ordinary siteforge_app
role, the only one available in production, is now sufficient on its
own.
"""
from sqlalchemy import text


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


class TestEmailTenantIndex:
    def test_signup_creates_a_matching_index_row(self, client, db):
        r = client.post(
            "/v1/onboarding/signup",
            json={"company_name": "Index Test Co", "admin_email": "indextest@example.com", "admin_password": "correct horse battery staple"},
        )
        assert r.status_code == 201

        from app.models.core import EmailTenantIndex
        row = EmailTenantIndex.query.filter_by(email="indextest@example.com").first()
        assert row is not None
        assert str(row.tenant_id) == r.get_json()["tenant_id"]

    def test_login_works_using_only_the_ordinary_app_role(self, client, db):
        """The actual regression: login must succeed without any
        special database role or elevated privilege, since that's
        exactly what production doesn't have."""
        client.post(
            "/v1/onboarding/signup",
            json={"company_name": "Login Test Co", "admin_email": "logintest@example.com", "admin_password": "correct horse battery staple"},
        )

        r = client.post("/v1/auth/login", json={"email": "logintest@example.com", "password": "correct horse battery staple"})
        assert r.status_code == 200
        assert r.get_json()["access_token"]
        assert r.get_json()["refresh_token"]

    def test_login_after_signup_is_a_genuinely_separate_request(self, client, db):
        """Signup auto-logs in via tokens it returns directly -- this
        confirms a real, independent subsequent login call (the thing
        that was actually broken; signup's own auto-login never
        exercised this code path at all) also works."""
        signup_body = client.post(
            "/v1/onboarding/signup",
            json={"company_name": "Separate Login Co", "admin_email": "separate@example.com", "admin_password": "correct horse battery staple"},
        ).get_json()

        login_body = client.post(
            "/v1/auth/login", json={"email": "separate@example.com", "password": "correct horse battery staple"}
        ).get_json()

        assert login_body["access_token"] != signup_body["access_token"]

    def test_wrong_password_still_rejected(self, client, db):
        client.post(
            "/v1/onboarding/signup",
            json={"company_name": "Wrong Pw Co", "admin_email": "wrongpw@example.com", "admin_password": "correct horse battery staple"},
        )
        r = client.post("/v1/auth/login", json={"email": "wrongpw@example.com", "password": "not the right password"})
        assert r.status_code == 401

    def test_nonexistent_email_rejected_cleanly(self, client, db):
        r = client.post("/v1/auth/login", json={"email": "never-signed-up@example.com", "password": "anything"})
        assert r.status_code == 401

    def test_inactive_user_cannot_log_in(self, client, db, seed_tenants):
        from app.auth.jwt_utils import hash_password
        from app.models.core import User, EmailTenantIndex

        _as_tenant(db, seed_tenants["a"])
        user = User(
            tenant_id=seed_tenants["a"],
            email="inactive@example.com",
            password_hash=hash_password("correct horse battery staple"),
            status="inactive",
        )
        db.session.add(user)
        db.session.flush()
        db.session.add(EmailTenantIndex(email=user.email, user_id=user.id, tenant_id=seed_tenants["a"]))
        db.session.commit()

        r = client.post("/v1/auth/login", json={"email": "inactive@example.com", "password": "correct horse battery staple"})
        assert r.status_code == 401
