"""Changing your password inside a portal ends every other session of that
user, while the session that made the change is handed fresh tokens."""
import pytest

from tests.test_portal_password_reset import PORTALS, _request_token


def _login(client, portal, email, password="a real password"):
    r = client.post(f"/v1/{portal}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return r.get_json()


def _auth(tokens, key="access_token"):
    return {"Authorization": f"Bearer {tokens[key]}"}


def _me(client, portal, tokens):
    return client.get(f"/v1/{portal}/auth/me", headers=_auth(tokens)).status_code


def _refresh(client, portal, tokens):
    return client.post(f"/v1/{portal}/auth/refresh", headers=_auth(tokens, "refresh_token")).status_code


def _change(client, portal, tokens, current="a real password", new="brand new pass 9"):
    return client.post(f"/v1/{portal}/auth/me/password", headers=_auth(tokens), json={"current_password": current, "new_password": new})


@pytest.mark.parametrize("portal", ["scp", "vnp", "clp"])
class TestPasswordChangeEndsOtherSessions:
    def _two_sessions(self, db, client, seed_tenants, portal):
        cfg = PORTALS[portal]
        cfg["seed"](db, seed_tenants["a"])
        return cfg, _login(client, portal, cfg["email"]), _login(client, portal, cfg["email"])

    def test_other_session_dies_and_current_one_gets_fresh_tokens(self, app, db, client, seed_tenants, portal):
        cfg, mine, other = self._two_sessions(db, client, seed_tenants, portal)
        assert _me(client, portal, mine) == 200 and _me(client, portal, other) == 200

        r = _change(client, portal, mine)
        assert r.status_code == 200
        fresh = r.get_json()
        assert fresh["status"] == "password updated"
        assert fresh["access_token"] and fresh["refresh_token"]

        assert _me(client, portal, other) == 401          # other browser signed out
        assert _refresh(client, portal, other) in (401, 422)  # and cannot refresh its way back
        assert _me(client, portal, mine) == 401           # the pre-change token is dead too
        assert _me(client, portal, fresh) == 200          # ...but the fresh pair works
        assert _refresh(client, portal, fresh) == 200

    def test_old_password_stops_working_new_one_works(self, app, db, client, seed_tenants, portal):
        cfg, mine, _ = self._two_sessions(db, client, seed_tenants, portal)
        _change(client, portal, mine)
        assert client.post(f"/v1/{portal}/auth/login", json={"email": cfg["email"], "password": "a real password"}).status_code == 401
        assert client.post(f"/v1/{portal}/auth/login", json={"email": cfg["email"], "password": "brand new pass 9"}).status_code == 200

    def test_wrong_current_password_changes_nothing(self, app, db, client, seed_tenants, portal):
        cfg, mine, other = self._two_sessions(db, client, seed_tenants, portal)
        assert _change(client, portal, mine, current="wrong password").status_code == 401
        assert _me(client, portal, mine) == 200 and _me(client, portal, other) == 200

    def test_too_short_new_password_is_refused_and_sessions_survive(self, app, db, client, seed_tenants, portal):
        cfg, mine, other = self._two_sessions(db, client, seed_tenants, portal)
        assert _change(client, portal, mine, new="short").status_code == 422
        assert _me(client, portal, other) == 200

    def test_an_emailed_reset_link_requested_earlier_no_longer_works(self, app, db, client, seed_tenants, portal):
        cfg, mine, _ = self._two_sessions(db, client, seed_tenants, portal)
        link_token = _request_token(client, portal, cfg["email"])[0][0]
        assert _change(client, portal, mine).status_code == 200
        r = client.post(f"/v1/{portal}/auth/reset-password", json={"token": link_token, "new_password": "attacker pass 77"})
        assert r.status_code == 400
        assert client.post(f"/v1/{portal}/auth/login", json={"email": cfg["email"], "password": "brand new pass 9"}).status_code == 200

    def test_changing_twice_keeps_only_the_latest_session(self, app, db, client, seed_tenants, portal):
        cfg, mine, _ = self._two_sessions(db, client, seed_tenants, portal)
        first = _change(client, portal, mine).get_json()
        second = _change(client, portal, first, current="brand new pass 9", new="another good pass 3").get_json()
        assert _me(client, portal, first) == 401
        assert _me(client, portal, second) == 200
