"""Per-user, per-category notification preferences."""
import uuid
from unittest.mock import patch

from sqlalchemy import text


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


class TestPreferencesApi:
    def test_defaults_are_all_on(self, client, seed_tenants, auth_headers):
        h = auth_headers("a", user_id=uuid.uuid4())
        r = client.get("/v1/notifications/preferences", headers=h)
        assert r.status_code == 200
        prefs = {p["category"]: p for p in r.get_json()["preferences"]}
        assert set(prefs) == {"approvals", "projects", "finance", "hse", "system"}
        assert all(p["in_app"] and p["email"] for p in prefs.values())

    def test_put_upserts_and_leaves_other_categories(self, client, seed_tenants, auth_headers):
        h = auth_headers("a", user_id=uuid.uuid4())
        body = {"preferences": [{"category": "finance", "in_app": False, "email": True}]}
        assert client.put("/v1/notifications/preferences", json=body, headers=h).status_code == 200
        body = {"preferences": [{"category": "finance", "in_app": False, "email": False}]}
        r = client.put("/v1/notifications/preferences", json=body, headers=h)
        prefs = {p["category"]: p for p in r.get_json()["preferences"]}
        assert prefs["finance"] == {"category": "finance", "in_app": False, "email": False}
        assert prefs["approvals"]["in_app"] is True

    def test_rejects_unknown_category(self, client, seed_tenants, auth_headers):
        h = auth_headers("a", user_id=uuid.uuid4())
        body = {"preferences": [{"category": "bogus", "in_app": True, "email": True}]}
        assert client.put("/v1/notifications/preferences", json=body, headers=h).status_code == 400

    def test_preferences_are_per_user(self, client, seed_tenants, auth_headers):
        u1, u2 = uuid.uuid4(), uuid.uuid4()
        body = {"preferences": [{"category": "hse", "in_app": False, "email": False}]}
        client.put("/v1/notifications/preferences", json=body, headers=auth_headers("a", user_id=u1))
        r = client.get("/v1/notifications/preferences", headers=auth_headers("a", user_id=u2))
        assert {p["category"]: p for p in r.get_json()["preferences"]}["hse"]["in_app"] is True


class TestNotifyHonorsPreferences:
    def _set(self, db, tenant, user, category, in_app, email):
        from app.notifications import services

        services.set_preferences(tenant, user_id=user, items=[{"category": category, "in_app": in_app, "email": email}])
        _as_tenant(db, tenant)

    def test_in_app_off_suppresses_row(self, app, db, seed_tenants):
        from app.notifications import services
        from app.notifications.models import Notification

        t, u = seed_tenants["a"], uuid.uuid4()
        _as_tenant(db, t)
        self._set(db, t, u, "approvals", False, True)
        assert services.notify(t, user_id=u, type="workflow.approval_requested", title="x") is None
        # a different category is unaffected
        assert services.notify(t, user_id=u, type="clp.request_resolved", title="y") is not None
        db.session.commit()
        assert Notification.query.filter_by(tenant_id=t, user_id=u).count() == 1

    def test_email_off_skips_dispatch_but_keeps_row(self, app, db, seed_tenants):
        from app.notifications import services

        t, u = seed_tenants["a"], uuid.uuid4()
        _as_tenant(db, t)
        self._set(db, t, u, "approvals", True, False)
        with patch.object(services, "_dispatch_external") as d:
            n = services.notify(t, user_id=u, type="workflow.escalated", title="x", channel="email")
        assert n is not None
        d.assert_not_called()

    def test_email_still_sent_when_only_in_app_off(self, app, db, seed_tenants):
        from app.notifications import services

        t, u = seed_tenants["a"], uuid.uuid4()
        _as_tenant(db, t)
        self._set(db, t, u, "approvals", False, True)
        with patch.object(services, "_dispatch_external") as d:
            n = services.notify(t, user_id=u, type="workflow.escalated", title="x", channel="email")
        assert n is None
        d.assert_called_once()

    def test_default_sends_email_for_email_channel(self, app, db, seed_tenants):
        from app.notifications import services

        t, u = seed_tenants["a"], uuid.uuid4()
        _as_tenant(db, t)
        with patch.object(services, "_dispatch_external") as d:
            services.notify(t, user_id=u, type="workflow.escalated", title="x", channel="email")
        d.assert_called_once()

    def test_notify_many_drops_suppressed_recipients(self, app, db, seed_tenants):
        from app.notifications import services

        t, u1, u2 = seed_tenants["a"], uuid.uuid4(), uuid.uuid4()
        _as_tenant(db, t)
        self._set(db, t, u1, "finance", False, False)
        out = services.notify_many(t, user_ids=[u1, u2], type="fin.invoice", title="x")
        assert [n.user_id for n in out] == [u2]
