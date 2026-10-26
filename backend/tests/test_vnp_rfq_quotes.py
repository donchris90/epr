"""Vendor portal: RFQ invitation listing and quote submission rules."""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def _vendor_with_user(db, tenant_id, email):
    from app.auth.jwt_utils import hash_password
    from app.modules.prc.models import Vendor
    from app.modules.vnp.models import VendorPortalUser, VendorPortalEmailIndex

    _as_tenant(db, tenant_id)
    vendor = Vendor(tenant_id=tenant_id, name=f"Vendor {email}")
    db.session.add(vendor)
    db.session.flush()
    user = VendorPortalUser(
        tenant_id=tenant_id, vendor_id=vendor.id, email=email,
        password_hash=hash_password("a real password"), is_active=True,
    )
    db.session.add(user)
    db.session.flush()
    ids = (vendor.id, user.id)
    db.session.add(VendorPortalEmailIndex(email=email, vendor_user_id=user.id, tenant_id=tenant_id))
    db.session.commit()
    return ids


def _rfq(db, tenant_id, vendor_ids, *, title="Cement supply", status="open", deadline=None):
    from app.modules.prc.models import RFQ, RFQInvitation

    _as_tenant(db, tenant_id)
    rfq = RFQ(tenant_id=tenant_id, title=title, status=status, response_deadline=deadline)
    db.session.add(rfq)
    db.session.flush()
    rfq_id = rfq.id
    for vid in vendor_ids:
        db.session.add(RFQInvitation(tenant_id=tenant_id, rfq_id=rfq_id, vendor_id=vid))
    db.session.commit()
    return rfq_id


def _login(client, email):
    r = client.post("/v1/vnp/auth/login", json={"email": email, "password": "a real password"})
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


def _quote(client, headers, user_id, rfq_id, price="1000.00"):
    return client.post(
        f"/v1/vnp/vendor-users/{user_id}/quotes",
        json={"rfq_id": str(rfq_id), "price": price, "lead_time_days": 7, "payment_terms": "Net 30"},
        headers=headers,
    )


class TestRfqInvitations:
    def test_lists_only_own_invitations_and_never_other_vendors_quotes(self, app, db, client, seed_tenants):
        t = seed_tenants["a"]
        v1, u1 = _vendor_with_user(db, t, "one@example.com")
        v2, u2 = _vendor_with_user(db, t, "two@example.com")
        shared = _rfq(db, t, [v1, v2], title="Shared")
        only2 = _rfq(db, t, [v2], title="Only vendor two")
        h1, h2 = _login(client, "one@example.com"), _login(client, "two@example.com")
        assert _quote(client, h2, u2, shared, "555.00").status_code == 201

        rows = client.get(f"/v1/vnp/vendor-users/{u1}/rfq-invitations", headers=h1).get_json()["data"]
        assert [r["title"] for r in rows] == ["Shared"]
        assert rows[0]["quote"] is None and rows[0]["can_quote"] is True
        assert str(only2) not in str(rows)
        assert "555" not in str(rows)

    def test_vendor_cannot_list_another_vendors_invitations(self, app, db, client, seed_tenants):
        t = seed_tenants["a"]
        _, u1 = _vendor_with_user(db, t, "one@example.com")
        _, u2 = _vendor_with_user(db, t, "two@example.com")
        h1 = _login(client, "one@example.com")
        assert client.get(f"/v1/vnp/vendor-users/{u2}/rfq-invitations", headers=h1).status_code == 403

    def test_quote_shows_up_and_invitation_marked_responded(self, app, db, client, seed_tenants):
        t = seed_tenants["a"]
        v, u = _vendor_with_user(db, t, "one@example.com")
        rfq = _rfq(db, t, [v])
        h = _login(client, "one@example.com")
        assert _quote(client, h, u, rfq).status_code == 201
        row = client.get(f"/v1/vnp/vendor-users/{u}/rfq-invitations", headers=h).get_json()["data"][0]
        assert row["invitation_status"] == "responded"
        assert row["can_quote"] is False
        assert row["quote"]["price"] == "1000.0000" or float(row["quote"]["price"]) == 1000.0
        assert row["quote"]["lead_time_days"] == 7

    def test_second_quote_rejected(self, app, db, client, seed_tenants):
        t = seed_tenants["a"]
        v, u = _vendor_with_user(db, t, "one@example.com")
        rfq = _rfq(db, t, [v])
        h = _login(client, "one@example.com")
        assert _quote(client, h, u, rfq).status_code == 201
        assert _quote(client, h, u, rfq).status_code == 409

    def test_closed_rfq_rejects_quote_and_cannot_quote(self, app, db, client, seed_tenants):
        t = seed_tenants["a"]
        v, u = _vendor_with_user(db, t, "one@example.com")
        rfq = _rfq(db, t, [v], status="closed")
        h = _login(client, "one@example.com")
        assert _quote(client, h, u, rfq).status_code == 409
        row = client.get(f"/v1/vnp/vendor-users/{u}/rfq-invitations", headers=h).get_json()["data"][0]
        assert row["can_quote"] is False

    def test_past_deadline_rejects_quote(self, app, db, client, seed_tenants):
        t = seed_tenants["a"]
        v, u = _vendor_with_user(db, t, "one@example.com")
        rfq = _rfq(db, t, [v], deadline=datetime.now(timezone.utc) - timedelta(hours=1))
        h = _login(client, "one@example.com")
        assert _quote(client, h, u, rfq).status_code == 409

    def test_future_deadline_allows_quote(self, app, db, client, seed_tenants):
        t = seed_tenants["a"]
        v, u = _vendor_with_user(db, t, "one@example.com")
        rfq = _rfq(db, t, [v], deadline=datetime.now(timezone.utc) + timedelta(days=2))
        h = _login(client, "one@example.com")
        assert _quote(client, h, u, rfq).status_code == 201

    def test_not_invited_still_403(self, app, db, client, seed_tenants):
        t = seed_tenants["a"]
        v1, u1 = _vendor_with_user(db, t, "one@example.com")
        v2, _ = _vendor_with_user(db, t, "two@example.com")
        rfq = _rfq(db, t, [v2])
        h = _login(client, "one@example.com")
        assert _quote(client, h, u1, rfq).status_code == 403


class TestInviteNotifiesVendor:
    def test_invite_notifies_only_that_vendors_users(self, app, db, client, seed_tenants, auth_headers):
        from app.modules.prc.models import RFQ

        t = seed_tenants["a"]
        v1, _ = _vendor_with_user(db, t, "one@example.com")
        v2, _ = _vendor_with_user(db, t, "two@example.com")
        _as_tenant(db, t)
        rfq = RFQ(tenant_id=t, title="Rebar", response_deadline=datetime.now(timezone.utc) + timedelta(days=3))
        db.session.add(rfq)
        db.session.flush()
        rfq_id = rfq.id
        db.session.commit()

        staff = auth_headers("a", permissions=["prc:write"])
        r = client.post(f"/v1/prc/rfqs/{rfq_id}/invite", json={"vendor_id": str(v1)}, headers=staff)
        assert r.status_code == 201

        n1 = client.get("/v1/notifications", headers=_login(client, "one@example.com")).get_json()["data"]
        n2 = client.get("/v1/notifications", headers=_login(client, "two@example.com")).get_json()["data"]
        assert [n["type"] for n in n1] == ["vnp.rfq_invited"]
        assert "Rebar" in n1[0]["title"]
        assert n1[0]["data"]["entity_id"] == str(rfq_id)
        assert n2 == []

    def test_duplicate_invite_creates_no_second_notification(self, app, db, client, seed_tenants, auth_headers):
        t = seed_tenants["a"]
        v1, _ = _vendor_with_user(db, t, "one@example.com")
        rfq_id = _rfq(db, t, [])
        staff = auth_headers("a", permissions=["prc:write"])
        assert client.post(f"/v1/prc/rfqs/{rfq_id}/invite", json={"vendor_id": str(v1)}, headers=staff).status_code == 201
        assert client.post(f"/v1/prc/rfqs/{rfq_id}/invite", json={"vendor_id": str(v1)}, headers=staff).status_code == 409
        n = client.get("/v1/notifications", headers=_login(client, "one@example.com")).get_json()["data"]
        assert len(n) == 1


class TestDeclineInvitation:
    def _decline(self, client, h, u, rfq, reason=None):
        return client.post(f"/v1/vnp/vendor-users/{u}/rfq-invitations/{rfq}/decline", json={"reason": reason}, headers=h)

    def test_decline_records_reason_blocks_quote_and_notifies_procurement(self, app, db, client, seed_tenants, auth_headers):
        t = seed_tenants["a"]
        v, u = _vendor_with_user(db, t, "one@example.com")
        rfq = _rfq(db, t, [v])
        h = _login(client, "one@example.com")
        r = self._decline(client, h, u, rfq, "Out of capacity")
        assert r.status_code == 200 and r.get_json()["invitation_status"] == "declined"
        row = client.get(f"/v1/vnp/vendor-users/{u}/rfq-invitations", headers=h).get_json()["data"][0]
        assert row["invitation_status"] == "declined" and row["decline_reason"] == "Out of capacity"
        assert row["can_quote"] is False and row["can_decline"] is False
        assert _quote(client, h, u, rfq).status_code == 409
        assert self._decline(client, h, u, rfq).status_code == 409

    def test_cannot_decline_after_quoting_or_when_closed_or_uninvited(self, app, db, client, seed_tenants):
        t = seed_tenants["a"]
        v1, u1 = _vendor_with_user(db, t, "one@example.com")
        v2, _ = _vendor_with_user(db, t, "two@example.com")
        quoted = _rfq(db, t, [v1])
        closed = _rfq(db, t, [v1], status="closed")
        other = _rfq(db, t, [v2])
        h = _login(client, "one@example.com")
        assert _quote(client, h, u1, quoted).status_code == 201
        assert self._decline(client, h, u1, quoted).status_code == 409
        assert self._decline(client, h, u1, closed).status_code == 409
        assert self._decline(client, h, u1, other).status_code == 403

    def test_procurement_staff_are_notified(self, app, db, client, seed_tenants, auth_headers):
        from app.models.core import User, Role
        from app.auth.jwt_utils import hash_password

        t = seed_tenants["a"]
        v, u = _vendor_with_user(db, t, "one@example.com")
        rfq = _rfq(db, t, [v])
        # a staff user holding prc:write
        _as_tenant(db, t)
        role = Role(tenant_id=t, name="Buyer", permission_set=["prc:write"])
        db.session.add(role)
        db.session.flush()
        staff = User(tenant_id=t, email="buyer@example.com", password_hash=hash_password("pw-12345678"), role_id=role.id, status="active")
        db.session.add(staff)
        db.session.commit()
        h = _login(client, "one@example.com")
        assert self._decline(client, h, u, rfq, "No stock").status_code == 200
        from app.notifications.models import Notification

        _as_tenant(db, t)
        rows = Notification.query.filter_by(tenant_id=t, user_id=staff.id).all()
        assert [n.type for n in rows] == ["prc.rfq_declined"]
        assert "No stock" in rows[0].body and rows[0].data["entity_id"] == str(rfq)


class TestReviseQuote:
    def _revise(self, client, h, u, rfq, price="900.00"):
        return client.put(
            f"/v1/vnp/vendor-users/{u}/quotes/{rfq}",
            json={"price": price, "lead_time_days": 5, "payment_terms": "Net 14"}, headers=h,
        )

    def test_revise_updates_and_counts(self, app, db, client, seed_tenants):
        t = seed_tenants["a"]
        v, u = _vendor_with_user(db, t, "one@example.com")
        rfq = _rfq(db, t, [v])
        h = _login(client, "one@example.com")
        assert _quote(client, h, u, rfq).status_code == 201
        r = self._revise(client, h, u, rfq)
        assert r.status_code == 200
        body = r.get_json()
        assert float(body["price"]) == 900.0 and body["lead_time_days"] == 5 and body["revision_count"] == 1
        assert body["revised_at"] is not None
        assert self._revise(client, h, u, rfq, "800.00").get_json()["revision_count"] == 2
        row = client.get(f"/v1/vnp/vendor-users/{u}/rfq-invitations", headers=h).get_json()["data"][0]
        assert row["can_revise"] is True and float(row["quote"]["price"]) == 800.0

    def test_cannot_revise_without_quote_after_close_or_past_deadline_or_uninvited(self, app, db, client, seed_tenants):
        from app.modules.prc.models import RFQ

        t = seed_tenants["a"]
        v1, u1 = _vendor_with_user(db, t, "one@example.com")
        v2, _ = _vendor_with_user(db, t, "two@example.com")
        none = _rfq(db, t, [v1])
        to_close = _rfq(db, t, [v1])
        other = _rfq(db, t, [v2])
        h = _login(client, "one@example.com")
        assert self._revise(client, h, u1, none).status_code == 404
        assert _quote(client, h, u1, to_close).status_code == 201
        _as_tenant(db, t)
        RFQ.query.filter_by(id=to_close).update({"status": "closed"})
        db.session.commit()
        assert self._revise(client, h, u1, to_close).status_code == 409
        assert self._revise(client, h, u1, other).status_code == 403

    def test_revision_notifies_procurement_and_does_not_touch_other_vendors(self, app, db, client, seed_tenants):
        t = seed_tenants["a"]
        v1, u1 = _vendor_with_user(db, t, "one@example.com")
        v2, u2 = _vendor_with_user(db, t, "two@example.com")
        rfq = _rfq(db, t, [v1, v2])
        h1, h2 = _login(client, "one@example.com"), _login(client, "two@example.com")
        assert _quote(client, h1, u1, rfq, "100.00").status_code == 201
        assert _quote(client, h2, u2, rfq, "200.00").status_code == 201
        assert self._revise(client, h1, u1, rfq, "90.00").status_code == 200
        row2 = client.get(f"/v1/vnp/vendor-users/{u2}/rfq-invitations", headers=h2).get_json()["data"][0]
        assert float(row2["quote"]["price"]) == 200.0 and row2["quote"]["revision_count"] == 0


class TestInviteEmail:
    def test_invite_queues_email_to_each_active_vendor_user(self, app, db, client, seed_tenants, auth_headers, monkeypatch):
        from app.notifications import tasks

        sent = []
        monkeypatch.setattr(tasks.send_email_notification, "delay", lambda **kw: sent.append(kw))
        t = seed_tenants["a"]
        v1, _ = _vendor_with_user(db, t, "one@example.com")
        v2, _ = _vendor_with_user(db, t, "two@example.com")
        rfq = _rfq(db, t, [])
        staff = auth_headers("a", permissions=["prc:write"])
        assert client.post(f"/v1/prc/rfqs/{rfq}/invite", json={"vendor_id": str(v1)}, headers=staff).status_code == 201
        assert [m["to_address"] for m in sent] == ["one@example.com"]
        assert "Cement supply" in sent[0]["subject"]
        # a rejected duplicate sends nothing more
        client.post(f"/v1/prc/rfqs/{rfq}/invite", json={"vendor_id": str(v1)}, headers=staff)
        assert len(sent) == 1

    def test_email_failure_does_not_fail_the_invite(self, app, db, client, seed_tenants, auth_headers, monkeypatch):
        from app.notifications import tasks

        def boom(**kw):
            raise RuntimeError("broker down")

        monkeypatch.setattr(tasks.send_email_notification, "delay", boom)
        t = seed_tenants["a"]
        v1, _ = _vendor_with_user(db, t, "one@example.com")
        rfq = _rfq(db, t, [])
        staff = auth_headers("a", permissions=["prc:write"])
        assert client.post(f"/v1/prc/rfqs/{rfq}/invite", json={"vendor_id": str(v1)}, headers=staff).status_code == 201
