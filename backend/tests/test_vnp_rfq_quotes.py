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
