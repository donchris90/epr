"""Staff decisions notify the affected subcontractor / vendor portal users,
who read them through the ordinary /v1/notifications routes."""
import uuid

from sqlalchemy import text

from tests.test_scp import _seed_subcontractor_and_agreement


def _as_tenant(db, tid):
    db.session.execute(text("SET LOCAL app.tenant_id = :t"), {"t": str(tid)})


def _scp_user(db, tid, subcontractor_id, email, active=True):
    from app.auth.jwt_utils import hash_password
    from app.modules.scp.models import SubcontractorPortalUser, SubcontractorPortalEmailIndex

    _as_tenant(db, tid)
    u = SubcontractorPortalUser(tenant_id=tid, subcontractor_id=subcontractor_id, email=email,
                                password_hash=hash_password("a real password"), is_active=active)
    db.session.add(u)
    db.session.flush()
    uid = u.id
    db.session.add(SubcontractorPortalEmailIndex(email=email, portal_user_id=uid, tenant_id=tid))
    db.session.commit()
    return uid


def _vnp_user(db, tid, vendor_id, email):
    from app.auth.jwt_utils import hash_password
    from app.modules.vnp.models import VendorPortalUser, VendorPortalEmailIndex

    _as_tenant(db, tid)
    u = VendorPortalUser(tenant_id=tid, vendor_id=vendor_id, email=email,
                         password_hash=hash_password("a real password"), is_active=True)
    db.session.add(u)
    db.session.flush()
    uid = u.id
    db.session.add(VendorPortalEmailIndex(email=email, vendor_user_id=uid, tenant_id=tid))
    db.session.commit()
    return uid


def _login(client, portal, email):
    r = client.post(f"/v1/{portal}/auth/login", json={"email": email, "password": "a real password"})
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


def _claim(db, tid, agreement_id):
    from app.modules.sub.models import SubcontractClaim

    _as_tenant(db, tid)
    c = SubcontractClaim(tenant_id=tid, agreement_id=agreement_id, claim_type="delay",
                         description="x", claimed_days=2, status="submitted")
    db.session.add(c)
    db.session.flush()
    cid = c.id
    db.session.commit()
    return cid


class TestSubcontractorNotifications:
    def test_claim_decision_notifies_only_that_subcontractors_users(self, app, db, client, seed_tenants, auth_headers):
        tid = seed_tenants["a"]
        sub_id, agr_id = _seed_subcontractor_and_agreement(db, tid, name="Sub One")
        other_sub, _ = _seed_subcontractor_and_agreement(db, tid, name="Sub Two")
        _scp_user(db, tid, sub_id, "one@sub.com")
        _scp_user(db, tid, sub_id, "one-b@sub.com")
        _scp_user(db, tid, sub_id, "inactive@sub.com", active=False)
        _scp_user(db, tid, other_sub, "two@sub.com")
        claim_id = _claim(db, tid, agr_id)

        r = client.post(f"/v1/sub/claims/{claim_id}/review", headers=auth_headers("a", permissions=["sub:approve"]),
                        json={"decision": "rejected", "response_notes": "Not substantiated"})
        assert r.status_code == 200

        h = _login(client, "scp", "one@sub.com")
        items = client.get("/v1/notifications", headers=h).get_json()["data"]
        assert len(items) == 1
        assert items[0]["type"] == "scp.claim_rejected"
        assert items[0]["body"] == "Not substantiated"
        assert client.get("/v1/notifications/unread-count", headers=h).get_json()["unread_count"] == 1
        assert client.get("/v1/notifications", headers=_login(client, "scp", "one-b@sub.com")).get_json()["data"]
        assert client.get("/v1/notifications", headers=_login(client, "scp", "two@sub.com")).get_json()["data"] == []

        nid = items[0]["id"]
        assert client.post(f"/v1/notifications/{nid}/read", headers=h).status_code == 200
        assert client.get("/v1/notifications/unread-count", headers=h).get_json()["unread_count"] == 0

    def test_failed_decision_creates_no_notification(self, app, db, client, seed_tenants, auth_headers):
        tid = seed_tenants["a"]
        sub_id, agr_id = _seed_subcontractor_and_agreement(db, tid)
        _scp_user(db, tid, sub_id, "one@sub.com")
        claim_id = _claim(db, tid, agr_id)
        r = client.post(f"/v1/sub/claims/{claim_id}/review", headers=auth_headers("a", permissions=["sub:approve"]),
                        json={"decision": "bogus"})
        assert r.status_code >= 400
        assert client.get("/v1/notifications", headers=_login(client, "scp", "one@sub.com")).get_json()["data"] == []


class TestVendorNotifications:
    def _request(self, db, tid, email):
        from app.modules.prc.models import Vendor
        from app.modules.vnp.models import VendorBankingChangeRequest

        _as_tenant(db, tid)
        v = Vendor(tenant_id=tid, name="V", banking_details=None)
        db.session.add(v)
        db.session.flush()
        vid = v.id
        db.session.commit()
        uid = _vnp_user(db, tid, vid, email)
        _as_tenant(db, tid)
        req = VendorBankingChangeRequest(tenant_id=tid, vendor_user_id=uid, vendor_id=vid,
                                         proposed_banking_details={"bank_name": "X"})
        db.session.add(req)
        db.session.flush()
        rid = req.id
        db.session.commit()
        return rid

    def test_approval_and_rejection_notify_vendor(self, app, db, client, seed_tenants, auth_headers):
        tid = seed_tenants["a"]
        h = auth_headers("a", permissions=["vnp:finance_approve"])
        rid1 = self._request(db, tid, "v1@vendor.com")
        assert client.post(f"/v1/vnp/banking-change-requests/{rid1}/approve", headers=h).status_code == 200
        items = client.get("/v1/notifications", headers=_login(client, "vnp", "v1@vendor.com")).get_json()["data"]
        assert [i["type"] for i in items] == ["vnp.banking_change_approved"]

        rid2 = self._request(db, tid, "v2@vendor.com")
        r = client.post(f"/v1/vnp/banking-change-requests/{rid2}/reject", headers=h, json={"reason": "Account name mismatch"})
        assert r.status_code == 200
        items = client.get("/v1/notifications", headers=_login(client, "vnp", "v2@vendor.com")).get_json()["data"]
        assert items[0]["type"] == "vnp.banking_change_rejected"
        assert items[0]["body"] == "Account name mismatch"


class TestVendorOwnBankingRequests:
    def test_vendor_lists_only_own_requests_with_status_and_reason(self, app, db, client, seed_tenants, auth_headers):
        helper = TestVendorNotifications()
        tid = seed_tenants["a"]
        rid = helper._request(db, tid, "mine@vendor.com")
        helper._request(db, tid, "other@vendor.com")
        fin = auth_headers("a", permissions=["vnp:finance_approve"])
        client.post(f"/v1/vnp/banking-change-requests/{rid}/reject", headers=fin, json={"reason": "Name mismatch"})

        login = client.post("/v1/vnp/auth/login", json={"email": "mine@vendor.com", "password": "a real password"}).get_json()
        h = {"Authorization": f"Bearer {login['access_token']}"}
        me = client.get("/v1/vnp/auth/me", headers=h).get_json()["id"]

        r = client.get(f"/v1/vnp/vendor-users/{me}/banking-change-requests", headers=h)
        assert r.status_code == 200
        rows = r.get_json()["data"]
        assert [x["id"] for x in rows] == [str(rid)]
        assert rows[0]["status"] == "rejected" and rows[0]["rejection_reason"] == "Name mismatch"
        assert rows[0]["reviewed_at"]

    def test_vendor_cannot_list_another_vendors_requests(self, app, db, client, seed_tenants):
        helper = TestVendorNotifications()
        tid = seed_tenants["a"]
        helper._request(db, tid, "mine@vendor.com")
        other = _vnp_user(db, tid, uuid.uuid4(), "other2@vendor.com")
        login = client.post("/v1/vnp/auth/login", json={"email": "mine@vendor.com", "password": "a real password"}).get_json()
        h = {"Authorization": f"Bearer {login['access_token']}"}
        assert client.get(f"/v1/vnp/vendor-users/{other}/banking-change-requests", headers=h).status_code == 403
