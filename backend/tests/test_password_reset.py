"""
Tests for real, previously genuinely missing functionality: staff
forgot-password, reset-password, and change-password. Also covers the
pwd_ts session-invalidation mechanism these are built on (a real
password change/reset must invalidate every previously-issued token
immediately, on every device) -- see app/auth/jwt_utils.py's own
docstrings on build_auth_claims/check_pwd_ts_claim for the full
reasoning.
"""
from unittest.mock import patch
from datetime import datetime, timezone

from sqlalchemy import text


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def _seed_real_user(db, tenant_id, *, email="pwdtest@example.com", password="originalpassword123"):
    from app.models.core import User, EmailTenantIndex
    from app.auth.jwt_utils import hash_password

    _as_tenant(db, tenant_id)
    user = User(tenant_id=tenant_id, email=email, password_hash=hash_password(password), status="active")
    db.session.add(user)
    db.session.flush()
    user_id = user.id
    db.session.add(EmailTenantIndex(email=email, user_id=user_id, tenant_id=tenant_id))
    db.session.commit()
    return user_id


class TestForgotPassword:
    def test_real_account_gets_a_real_queued_reset_email(self, app, db, client, seed_tenants):
        _seed_real_user(db, seed_tenants["a"])

        with patch("app.notifications.tasks.send_email_notification.delay") as mock_delay:
            r = client.post("/v1/auth/forgot-password", json={"email": "pwdtest@example.com"})

        assert r.status_code == 200
        assert mock_delay.called

    def test_never_reveals_whether_an_account_exists(self, app, db, client, seed_tenants):
        """The real, explicit security requirement: identical responses
        for a real account and a fake one."""
        _seed_real_user(db, seed_tenants["a"])

        with patch("app.notifications.tasks.send_email_notification.delay"):
            r_real = client.post("/v1/auth/forgot-password", json={"email": "pwdtest@example.com"})
        r_fake = client.post("/v1/auth/forgot-password", json={"email": "definitely-not-real@example.com"})

        assert r_real.status_code == r_fake.status_code == 200
        assert r_real.get_json() == r_fake.get_json()

    def test_no_email_sent_for_a_nonexistent_account(self, app, db, client, seed_tenants):
        with patch("app.notifications.tasks.send_email_notification.delay") as mock_delay:
            r = client.post("/v1/auth/forgot-password", json={"email": "definitely-not-real@example.com"})

        assert r.status_code == 200
        assert not mock_delay.called

    def test_no_email_sent_for_a_suspended_account(self, app, db, client, seed_tenants):
        from app.models.core import User

        user_id = _seed_real_user(db, seed_tenants["a"], email="suspended@example.com")
        _as_tenant(db, seed_tenants["a"])
        User.query.filter_by(id=user_id).update({"status": "suspended"})
        db.session.commit()

        with patch("app.notifications.tasks.send_email_notification.delay") as mock_delay:
            r = client.post("/v1/auth/forgot-password", json={"email": "suspended@example.com"})

        assert r.status_code == 200
        assert not mock_delay.called

    def test_missing_email_field_is_a_clean_validation_error_not_a_crash(self, app, db, client):
        r = client.post("/v1/auth/forgot-password", json={})
        assert r.status_code == 422


class TestResetPassword:
    def _request_and_capture_token(self, db, client, tenant_id, email="pwdtest@example.com"):
        _seed_real_user(db, tenant_id, email=email)
        with patch("app.auth.services.secrets.token_urlsafe", return_value="real-test-token-abc"), patch(
            "app.notifications.tasks.send_email_notification.delay"
        ):
            client.post("/v1/auth/forgot-password", json={"email": email})
        return "real-test-token-abc"

    def test_real_token_resets_the_password(self, app, db, client, seed_tenants):
        token = self._request_and_capture_token(db, client, seed_tenants["a"])

        r = client.post("/v1/auth/reset-password", json={"token": token, "new_password": "brandnewpassword456"})
        assert r.status_code == 200

        r_login_old = client.post("/v1/auth/login", json={"email": "pwdtest@example.com", "password": "originalpassword123"})
        assert r_login_old.status_code == 401
        r_login_new = client.post("/v1/auth/login", json={"email": "pwdtest@example.com", "password": "brandnewpassword456"})
        assert r_login_new.status_code == 200

    def test_token_is_genuinely_single_use(self, app, db, client, seed_tenants):
        token = self._request_and_capture_token(db, client, seed_tenants["a"])

        r1 = client.post("/v1/auth/reset-password", json={"token": token, "new_password": "firstnewpassword456"})
        assert r1.status_code == 200

        r2 = client.post("/v1/auth/reset-password", json={"token": token, "new_password": "secondnewpassword789"})
        assert r2.status_code == 400

    def test_unknown_token_is_rejected(self, app, db, client):
        r = client.post("/v1/auth/reset-password", json={"token": "totally-made-up-token", "new_password": "newpassword456"})
        assert r.status_code == 400

    def test_expired_token_is_rejected(self, app, db, client, seed_tenants):
        from app.models.core import PasswordResetToken

        user_id = _seed_real_user(db, seed_tenants["a"])
        _as_tenant(db, seed_tenants["a"])
        token_hash_value = __import__("hashlib").sha256(b"real-expired-token").hexdigest()
        db.session.add(
            PasswordResetToken(
                tenant_id=seed_tenants["a"], user_id=user_id, token_hash=token_hash_value,
                expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            )
        )
        db.session.commit()

        r = client.post("/v1/auth/reset-password", json={"token": "real-expired-token", "new_password": "newpassword456"})
        assert r.status_code == 400

    def test_new_password_too_short_is_rejected(self, app, db, client, seed_tenants):
        token = self._request_and_capture_token(db, client, seed_tenants["a"])

        r = client.post("/v1/auth/reset-password", json={"token": token, "new_password": "short"})
        assert r.status_code == 422

    def test_reset_invalidates_every_previously_issued_session(self, app, db, client, seed_tenants):
        """The real, explicit requirement: a successful reset revokes
        existing sessions -- verified end to end, not just that
        password_changed_at gets set."""
        _seed_real_user(db, seed_tenants["a"])
        r_login = client.post("/v1/auth/login", json={"email": "pwdtest@example.com", "password": "originalpassword123"})
        old_access_token = r_login.get_json()["access_token"]

        with patch("app.auth.services.secrets.token_urlsafe", return_value="real-invalidation-token"), patch(
            "app.notifications.tasks.send_email_notification.delay"
        ):
            client.post("/v1/auth/forgot-password", json={"email": "pwdtest@example.com"})
        client.post("/v1/auth/reset-password", json={"token": "real-invalidation-token", "new_password": "brandnewpassword456"})

        r_old_session = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {old_access_token}"})
        assert r_old_session.status_code == 401


class TestChangePassword:
    def test_real_change_with_correct_current_password(self, app, db, client, seed_tenants, auth_headers):
        user_id = _seed_real_user(db, seed_tenants["a"])
        headers = auth_headers("a", user_id=str(user_id), permissions=["*"])

        r = client.put("/v1/auth/me/password", headers=headers, json={"current_password": "originalpassword123", "new_password": "brandnewpassword456"})
        assert r.status_code == 200

        r_login_new = client.post("/v1/auth/login", json={"email": "pwdtest@example.com", "password": "brandnewpassword456"})
        assert r_login_new.status_code == 200

    def test_wrong_current_password_is_rejected(self, app, db, client, seed_tenants, auth_headers):
        user_id = _seed_real_user(db, seed_tenants["a"])
        headers = auth_headers("a", user_id=str(user_id), permissions=["*"])

        r = client.put("/v1/auth/me/password", headers=headers, json={"current_password": "totallywrongpassword", "new_password": "brandnewpassword456"})
        assert r.status_code == 400

        # Real, original password must still work -- nothing changed
        r_login = client.post("/v1/auth/login", json={"email": "pwdtest@example.com", "password": "originalpassword123"})
        assert r_login.status_code == 200

    def test_new_password_too_short_is_rejected(self, app, db, client, seed_tenants, auth_headers):
        user_id = _seed_real_user(db, seed_tenants["a"])
        headers = auth_headers("a", user_id=str(user_id), permissions=["*"])

        r = client.put("/v1/auth/me/password", headers=headers, json={"current_password": "originalpassword123", "new_password": "short"})
        assert r.status_code == 422

    def test_requires_authentication(self, app, db, client):
        r = client.put("/v1/auth/me/password", json={"current_password": "x", "new_password": "newpassword456"})
        assert r.status_code == 401

    def test_change_invalidates_every_other_session_including_this_one(self, app, db, client, seed_tenants, auth_headers):
        user_id = _seed_real_user(db, seed_tenants["a"])
        headers = auth_headers("a", user_id=str(user_id), permissions=["*"])

        r_change = client.put("/v1/auth/me/password", headers=headers, json={"current_password": "originalpassword123", "new_password": "brandnewpassword456"})
        assert r_change.status_code == 200

        # The SAME session that just made this request is also now invalid
        r_after = client.get("/v1/auth/me", headers=headers)
        assert r_after.status_code == 401


class TestPasswordChangeSessionInvalidation:
    """Real, direct coverage of the pwd_ts mechanism itself (not just
    through the reset/change endpoints), including the real security
    gap found and fixed while building this: /v1/auth/refresh is
    exempt from the tenant-context middleware entirely (it takes a
    refresh token, not an access token) and previously never checked
    this at all."""

    def test_old_access_token_rejected_after_a_real_password_change(self, app, db, client, seed_tenants):
        user_id = _seed_real_user(db, seed_tenants["a"])
        r_login = client.post("/v1/auth/login", json={"email": "pwdtest@example.com", "password": "originalpassword123"})
        access_token = r_login.get_json()["access_token"]

        from app.models.core import User

        _as_tenant(db, seed_tenants["a"])
        User.query.filter_by(id=user_id).update({"password_changed_at": datetime.now(timezone.utc)})
        db.session.commit()

        r = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
        assert r.status_code == 401

    def test_old_refresh_token_also_rejected_after_a_real_password_change(self, app, db, client, seed_tenants):
        """Real regression test for the real gap found and fixed while
        building this: refresh() previously carried over old claims
        blindly with no database check at all, meaning an old refresh
        token could keep minting fresh access tokens forever after a
        password change."""
        user_id = _seed_real_user(db, seed_tenants["a"])
        r_login = client.post("/v1/auth/login", json={"email": "pwdtest@example.com", "password": "originalpassword123"})
        refresh_token = r_login.get_json()["refresh_token"]

        from app.models.core import User

        _as_tenant(db, seed_tenants["a"])
        User.query.filter_by(id=user_id).update({"password_changed_at": datetime.now(timezone.utc)})
        db.session.commit()

        r = client.post("/v1/auth/refresh", headers={"Authorization": f"Bearer {refresh_token}"})
        assert r.status_code == 401

    def test_a_token_never_changed_since_issuance_still_works(self, app, db, client, seed_tenants):
        """The real, correct baseline case -- a real user who has
        never changed their password must not be affected at all."""
        _seed_real_user(db, seed_tenants["a"])
        r_login = client.post("/v1/auth/login", json={"email": "pwdtest@example.com", "password": "originalpassword123"})
        access_token = r_login.get_json()["access_token"]

        r = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
        assert r.status_code == 200

    def test_synthetic_test_fixture_tokens_are_unaffected(self, app, db, client, seed_tenants, auth_headers):
        """Real regression test for a real fix made while verifying
        this batch: this codebase's own auth_headers test fixture
        commonly issues tokens for a synthetic, unconnected user_id
        (no real User row) across hundreds of existing tests -- the
        pwd_ts check must not reject these, since real production
        tokens are only ever issued for real users in the first place,
        and this scenario is purely a test-fixture artifact, not a
        real password-change situation this mechanism should react
        to."""
        headers = auth_headers("a", permissions=["*"])
        r = client.get("/v1/org/members", headers=headers)
        assert r.status_code == 200
