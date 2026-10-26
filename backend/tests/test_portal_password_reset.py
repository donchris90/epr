"""Self-service forgot/reset password for the SCP, VNP and CLP portals."""
import re
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import text

from tests.test_scp_vnp_portal_auth import _seed_scp_user, _seed_vnp_user

def _seed_clp_user(db, tenant_id, *, email="client@example.com", password="a real password"):
    from tests.test_clp_client_portal import _seed_client_user

    return _seed_client_user(db, tenant_id, email=email, password=password)


PORTALS = {
    "clp": {"seed": _seed_clp_user, "email": "client@example.com", "path": "/portal/reset-password"},
    "scp": {"seed": _seed_scp_user, "email": "sub@example.com", "path": "/subcontractor/reset-password"},
    "vnp": {"seed": _seed_vnp_user, "email": "vendor@example.com", "path": "/vendor/reset-password"},
}


def _request_token(client, portal, email):
    with patch("app.notifications.tasks.send_email_notification.delay") as mock_delay:
        r = client.post(f"/v1/{portal}/auth/forgot-password", json={"email": email})
    assert r.status_code == 200
    tokens = []
    for call in mock_delay.call_args_list:
        m = re.search(r"token=([\w-]+)", call.kwargs["body"])
        tokens.append((m.group(1), call.kwargs))
    return tokens


@pytest.mark.parametrize("portal", ["scp", "vnp", "clp"])
class TestPortalPasswordReset:
    def test_email_contains_portal_specific_link(self, app, db, client, seed_tenants, portal):
        cfg = PORTALS[portal]
        cfg["seed"](db, seed_tenants["a"])
        tokens = _request_token(client, portal, cfg["email"])
        assert len(tokens) == 1
        assert cfg["path"] in tokens[0][1]["body"]
        assert tokens[0][1]["to_address"] == cfg["email"]

    def test_never_reveals_whether_account_exists(self, app, db, client, seed_tenants, portal):
        cfg = PORTALS[portal]
        cfg["seed"](db, seed_tenants["a"])
        with patch("app.notifications.tasks.send_email_notification.delay") as d:
            real = client.post(f"/v1/{portal}/auth/forgot-password", json={"email": cfg["email"]})
            fake = client.post(f"/v1/{portal}/auth/forgot-password", json={"email": "nobody@example.com"})
        assert real.status_code == fake.status_code == 200
        assert real.get_json() == fake.get_json()
        assert d.call_count == 1

    def test_inactive_user_gets_no_email(self, app, db, client, seed_tenants, portal):
        cfg = PORTALS[portal]
        cfg["seed"](db, seed_tenants["a"])
        db.session.execute(text("SET LOCAL app.tenant_id = :t"), {"t": str(seed_tenants["a"])})
        table = {"scp": "scp_portal_users", "vnp": "vnp_portal_users", "clp": "clp_portal_users"}[portal]
        db.session.execute(text(f"UPDATE {table} SET is_active = false"))
        db.session.commit()
        assert _request_token(client, portal, cfg["email"]) == []

    def test_reset_then_login_with_new_password(self, app, db, client, seed_tenants, portal):
        cfg = PORTALS[portal]
        cfg["seed"](db, seed_tenants["a"], password="oldpassword1")
        token = _request_token(client, portal, cfg["email"])[0][0]
        r = client.post(f"/v1/{portal}/auth/reset-password", json={"token": token, "new_password": "brandnewpass1"})
        assert r.status_code == 200
        assert client.post(f"/v1/{portal}/auth/login", json={"email": cfg["email"], "password": "oldpassword1"}).status_code == 401
        assert client.post(f"/v1/{portal}/auth/login", json={"email": cfg["email"], "password": "brandnewpass1"}).status_code == 200

    def test_token_is_single_use(self, app, db, client, seed_tenants, portal):
        cfg = PORTALS[portal]
        cfg["seed"](db, seed_tenants["a"])
        token = _request_token(client, portal, cfg["email"])[0][0]
        body = {"token": token, "new_password": "brandnewpass1"}
        assert client.post(f"/v1/{portal}/auth/reset-password", json=body).status_code == 200
        assert client.post(f"/v1/{portal}/auth/reset-password", json=body).status_code == 400

    def test_expired_token_rejected(self, app, db, client, seed_tenants, portal):
        cfg = PORTALS[portal]
        cfg["seed"](db, seed_tenants["a"])
        token = _request_token(client, portal, cfg["email"])[0][0]
        db.session.execute(
            text("UPDATE portal_password_reset_tokens SET expires_at = :e"),
            {"e": datetime.now(timezone.utc) - timedelta(minutes=1)},
        )
        db.session.commit()
        r = client.post(f"/v1/{portal}/auth/reset-password", json={"token": token, "new_password": "brandnewpass1"})
        assert r.status_code == 400

    def test_garbage_token_and_short_password_rejected(self, app, db, client, seed_tenants, portal):
        assert client.post(f"/v1/{portal}/auth/reset-password", json={"token": "nope", "new_password": "brandnewpass1"}).status_code == 400
        assert client.post(f"/v1/{portal}/auth/reset-password", json={"token": "nope", "new_password": "short"}).status_code == 422

    def test_token_for_other_portal_does_not_work(self, app, db, client, seed_tenants, portal):
        cfg = PORTALS[portal]
        cfg["seed"](db, seed_tenants["a"])
        token = _request_token(client, portal, cfg["email"])[0][0]
        other = "vnp" if portal == "scp" else "scp" if portal == "clp" else "clp"
        r = client.post(f"/v1/{other}/auth/reset-password", json={"token": token, "new_password": "brandnewpass1"})
        assert r.status_code == 400

    def test_reset_invalidates_existing_sessions(self, app, db, client, seed_tenants, portal):
        cfg = PORTALS[portal]
        uid = cfg["seed"](db, seed_tenants["a"], password="oldpassword1")
        login = client.post(f"/v1/{portal}/auth/login", json={"email": cfg["email"], "password": "oldpassword1"}).get_json()
        h = {"Authorization": f"Bearer {login['access_token']}"}
        assert client.get(f"/v1/{portal}/auth/me", headers=h).status_code == 200

        token = _request_token(client, portal, cfg["email"])[0][0]
        client.post(f"/v1/{portal}/auth/reset-password", json={"token": token, "new_password": "brandnewpass1"})

        assert client.get(f"/v1/{portal}/auth/me", headers=h).status_code == 401
        r = client.post(f"/v1/{portal}/auth/refresh", headers={"Authorization": f"Bearer {login['refresh_token']}"})
        assert r.status_code == 401

        fresh = client.post(f"/v1/{portal}/auth/login", json={"email": cfg["email"], "password": "brandnewpass1"}).get_json()
        assert client.get(f"/v1/{portal}/auth/me", headers={"Authorization": f"Bearer {fresh['access_token']}"}).status_code == 200
        r = client.post(f"/v1/{portal}/auth/refresh", headers={"Authorization": f"Bearer {fresh['refresh_token']}"})
        assert r.status_code == 200
