"""Finance review list for vendor banking-change requests."""
from tests.test_portal_notifications import TestVendorNotifications, _as_tenant, _login


def _req(db, tid, email, *, current=None, proposed=None):
    from app.modules.prc.models import Vendor
    from app.modules.vnp.models import VendorBankingChangeRequest

    helper = TestVendorNotifications()
    rid = helper._request(db, tid, email)
    _as_tenant(db, tid)
    req = db.session.get(VendorBankingChangeRequest, rid)
    if proposed is not None:
        req.proposed_banking_details = proposed
    if current is not None:
        db.session.get(Vendor, req.vendor_id).banking_details = current
    vid = req.vendor_id
    db.session.commit()
    return rid, vid


class TestReviewList:
    def test_includes_vendor_name_and_current_details(self, app, db, client, seed_tenants, auth_headers):
        t = seed_tenants["a"]
        _req(db, t, "v@x.com", current={"account_number": "111"}, proposed={"account_number": "222"})
        h = auth_headers("a", permissions=["vnp:finance_approve"])
        row = client.get("/v1/vnp/banking-change-requests", headers=h).get_json()["data"][0]
        assert row["vendor_name"] == "V"
        assert row["current_banking_details"] == {"account_number": "111"}
        assert row["proposed_banking_details"] == {"account_number": "222"}

    def test_status_filter_and_all(self, app, db, client, seed_tenants, auth_headers):
        t = seed_tenants["a"]
        r1, _ = _req(db, t, "a@x.com")
        _req(db, t, "b@x.com")
        h = auth_headers("a", permissions=["vnp:finance_approve"])
        assert client.post(f"/v1/vnp/banking-change-requests/{r1}/approve", headers=h).status_code == 200
        get = lambda s: client.get(f"/v1/vnp/banking-change-requests?status={s}", headers=h).get_json()["data"]
        assert len(get("pending")) == 1
        assert len(get("approved")) == 1
        assert len(get("all")) == 2
        assert client.get("/v1/vnp/banking-change-requests?status=bogus", headers=h).status_code == 400

    def test_approval_keeps_previous_details(self, app, db, client, seed_tenants, auth_headers):
        t = seed_tenants["a"]
        rid, _ = _req(db, t, "v@x.com", current={"account_number": "111"}, proposed={"account_number": "222"})
        h = auth_headers("a", permissions=["vnp:finance_approve"])
        client.post(f"/v1/vnp/banking-change-requests/{rid}/approve", headers=h)
        row = client.get("/v1/vnp/banking-change-requests?status=approved", headers=h).get_json()["data"][0]
        assert row["previous_banking_details"] == {"account_number": "111"}
        assert row["current_banking_details"] == {"account_number": "222"}

    def test_vendor_never_sees_previous_or_current_details(self, app, db, client, seed_tenants):
        t = seed_tenants["a"]
        rid, _ = _req(db, t, "v@x.com", current={"account_number": "111"})
        from app.modules.vnp.models import VendorBankingChangeRequest

        _as_tenant(db, t)
        uid = db.session.get(VendorBankingChangeRequest, rid).vendor_user_id
        db.session.commit()
        h = _login(client, "vnp", "v@x.com")
        body = client.get(f"/v1/vnp/vendor-users/{uid}/banking-change-requests", headers=h).get_json()
        assert "previous_banking_details" not in str(body)
        assert "current_banking_details" not in str(body)

    def test_requires_finance_permission(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a", permissions=["prc:read"])
        assert client.get("/v1/vnp/banking-change-requests", headers=h).status_code == 403
