"""
Tests for the real POST /v1/auth/{login,refresh,logout} HTTP flow.

Every other test in this suite authenticates via the `auth_headers`
fixture, which calls `create_access_token` directly -- a deliberate
shortcut that skips the actual login endpoint, password verification,
and refresh-token issuance entirely. That shortcut is correct for
testing business logic in the other 25 modules, but it also means this
flow itself had zero coverage: a real bug (the tenant-context
middleware rejecting valid refresh tokens on /logout, because only
/refresh was exempted from its default access-token assumption) went
undetected across the entire build until it was found by manually
driving these exact endpoints. These tests exist to make sure that
class of regression gets caught automatically from now on.
"""
import pytest


def _login(client, email="real-login-test@example.com", password="correct horse battery staple"):
    return client.post("/v1/auth/login", json={"email": email, "password": password})


class TestLogin:
    def test_login_with_correct_credentials_returns_both_tokens(self, client, real_user):
        r = _login(client)
        assert r.status_code == 200
        body = r.get_json()
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["access_token"] != body["refresh_token"]

    def test_login_with_wrong_password_rejected(self, client, real_user):
        r = _login(client, password="wrong password")
        assert r.status_code == 401

    def test_login_with_unknown_email_rejected(self, client, real_user):
        r = _login(client, email="nobody@example.com")
        assert r.status_code == 401

    def test_access_token_works_on_a_real_protected_route(self, client, real_user):
        access_token = _login(client).get_json()["access_token"]
        r = client.get("/v1/prc/vendors", headers={"Authorization": f"Bearer {access_token}"})
        # The seeded user has no role/permissions, so this is a 403
        # (authenticated but not authorized) -- the meaningful
        # assertion is that it's NOT 401, i.e. the token itself was
        # accepted as valid by the real request pipeline.
        assert r.status_code == 403


class TestRefreshRotation:
    """Business rule: a refresh token is single-use. Each call to
    /refresh issues a new refresh token and immediately revokes the
    one just used, so a leaked-and-reused token is both bounded in
    damage and detectable."""

    def test_refresh_issues_new_access_and_refresh_tokens(self, client, real_user):
        tokens = _login(client).get_json()
        r = client.post("/v1/auth/refresh", headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
        assert r.status_code == 200
        new_tokens = r.get_json()
        assert new_tokens["access_token"] != tokens["access_token"]
        assert new_tokens["refresh_token"] != tokens["refresh_token"]

    def test_reusing_a_rotated_away_refresh_token_is_rejected(self, client, real_user):
        tokens = _login(client).get_json()
        original_refresh = tokens["refresh_token"]

        r = client.post("/v1/auth/refresh", headers={"Authorization": f"Bearer {original_refresh}"})
        assert r.status_code == 200

        # The old, now-rotated-away token must not work a second time.
        r = client.post("/v1/auth/refresh", headers={"Authorization": f"Bearer {original_refresh}"})
        assert r.status_code == 401

    def test_the_new_refresh_token_from_rotation_works(self, client, real_user):
        tokens = _login(client).get_json()
        rotated = client.post("/v1/auth/refresh", headers={"Authorization": f"Bearer {tokens['refresh_token']}"}).get_json()

        r = client.post("/v1/auth/refresh", headers={"Authorization": f"Bearer {rotated['refresh_token']}"})
        assert r.status_code == 200

    def test_an_access_token_cannot_be_used_to_refresh(self, client, real_user):
        tokens = _login(client).get_json()
        r = client.post("/v1/auth/refresh", headers={"Authorization": f"Bearer {tokens['access_token']}"})
        assert r.status_code == 422


class TestLogout:
    """Regression test for the real bug found while building this:
    /v1/auth/logout was unreachable with a valid refresh token because
    the tenant-context middleware's before_request only exempted
    /v1/auth/refresh from its own default access-token check, not
    /v1/auth/logout -- so every logout attempt was rejected before the
    route's own @jwt_required(refresh=True) ever ran."""

    def test_logout_with_a_valid_refresh_token_succeeds(self, client, real_user):
        tokens = _login(client).get_json()
        r = client.post("/v1/auth/logout", headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
        assert r.status_code == 200

    def test_refresh_token_is_rejected_after_logout(self, client, real_user):
        tokens = _login(client).get_json()
        client.post("/v1/auth/logout", headers={"Authorization": f"Bearer {tokens['refresh_token']}"})

        r = client.post("/v1/auth/refresh", headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
        assert r.status_code == 401

    def test_logout_does_not_invalidate_the_already_issued_access_token(self, client, real_user):
        """Access tokens are deliberately NOT checked against the
        revocation blocklist (see JWT_BLOCKLIST_TOKEN_CHECKS in
        config.py) -- they're short-lived by design, and checking them
        would cost a Redis round-trip on every single API request for
        no real benefit. Logging out revokes the ability to get NEW
        access tokens, not the one already issued."""
        tokens = _login(client).get_json()
        client.post("/v1/auth/logout", headers={"Authorization": f"Bearer {tokens['refresh_token']}"})

        r = client.get("/v1/prc/vendors", headers={"Authorization": f"Bearer {tokens['access_token']}"})
        assert r.status_code == 403  # still authenticated (not 401); just unauthorized, as before logout
