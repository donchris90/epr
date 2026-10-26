"""DSAR request tracking and erasure (anonymisation)."""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from tests.test_dsar import _as_tenant


def _mk(client, headers, **over):
    body = {"request_type": "erasure", "subject_name": "Jane Doe", "subject_email": "jane@example.com"}
    body.update(over)
    return client.post("/v1/dsar/requests", headers=headers, json=body)


class TestRequestTracking:
    def test_create_sets_30_day_due_date(self, app, db, client, seed_tenants, auth_headers):
        r = _mk(client, auth_headers("a", permissions=["dsar:manage"]))
        assert r.status_code == 201
        b = r.get_json()
        recv, due = (datetime.fromisoformat(b[k]) for k in ("received_at", "due_at"))
        assert due - recv == timedelta(days=30)
        assert b["status"] == "open" and b["is_overdue"] is False

    def test_requires_manage_permission(self, app, db, client, seed_tenants, auth_headers):
        assert _mk(client, auth_headers("a", permissions=["dsar:search"])).status_code == 403

    def test_invalid_type_rejected(self, app, db, client, seed_tenants, auth_headers):
        assert _mk(client, auth_headers("a", permissions=["dsar:manage"]), request_type="bogus").status_code == 400

    def test_overdue_flag_and_list_filter(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a", permissions=["dsar:manage"])
        rid = _mk(client, h).get_json()["id"]
        _as_tenant(db, seed_tenants["a"])
        db.session.execute(text("UPDATE dsar_requests SET due_at = :d"), {"d": datetime.now(timezone.utc) - timedelta(days=1)})
        db.session.commit()
        got = client.get(f"/v1/dsar/requests/{rid}", headers=h).get_json()
        assert got["is_overdue"] is True
        assert len(client.get("/v1/dsar/requests?status=open", headers=h).get_json()["data"]) == 1
        assert client.get("/v1/dsar/requests?status=completed", headers=h).get_json()["data"] == []

    def test_close_and_reject_rules(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a", permissions=["dsar:manage"])
        rid = _mk(client, h).get_json()["id"]
        assert client.patch(f"/v1/dsar/requests/{rid}", headers=h, json={"status": "rejected"}).status_code == 400
        r = client.patch(f"/v1/dsar/requests/{rid}", headers=h, json={"status": "completed", "resolution_notes": "Done"})
        assert r.status_code == 200 and r.get_json()["resolved_at"]
        assert client.patch(f"/v1/dsar/requests/{rid}", headers=h, json={"status": "open"}).status_code == 409

    def test_other_tenant_cannot_see_request(self, app, db, client, seed_tenants, auth_headers):
        rid = _mk(client, auth_headers("a", permissions=["dsar:manage"])).get_json()["id"]
        assert client.get(f"/v1/dsar/requests/{rid}", headers=auth_headers("b", permissions=["dsar:manage"])).status_code == 404


class TestErasure:
    def _seed(self, db, tid):
        from app.auth.jwt_utils import hash_password
        from app.modules.bdc.models import Contact
        from app.modules.vnp.models import VendorPortalUser, VendorPortalEmailIndex
        from app.modules.wfm.models import CasualWorker

        _as_tenant(db, tid)
        c = Contact(tenant_id=tid, name="Jane Doe", email="jane@example.com", phone="0801")
        w = CasualWorker(tenant_id=tid, name="Jane Doe", phone="0801", id_number="NIN123")
        v = VendorPortalUser(tenant_id=tid, vendor_id=uuid.uuid4(), email="jane@example.com",
                             password_hash=hash_password("a real password"), is_active=True)
        db.session.add_all([c, w, v])
        db.session.flush()
        db.session.add(VendorPortalEmailIndex(email="jane@example.com", vendor_user_id=v.id, tenant_id=tid))
        ids = (c.id, w.id, v.id)
        db.session.commit()
        return ids

    def test_search_then_erase_anonymises_and_logs_ids_only(self, app, db, client, seed_tenants, auth_headers):
        tid = seed_tenants["a"]
        cid, wid, vid = self._seed(db, tid)
        h = auth_headers("a", permissions=["dsar:manage", "dsar:search"])
        rid = _mk(client, h).get_json()["id"]

        found = client.get("/v1/dsar/search?email=jane@example.com", headers=h).get_json()
        assert "vnp_portal_users" in found["results"]

        r = client.post(f"/v1/dsar/requests/{rid}/erase", headers=h, json={"records": [
            {"table": "bdc_contacts", "id": str(cid)},
            {"table": "wfm_casual_workers", "id": str(wid)},
            {"table": "vnp_portal_users", "id": str(vid)},
        ]})
        assert r.status_code == 200
        body = r.get_json()
        assert body["status"] == "in_progress" and len(body["actions"]) == 3
        assert "jane" not in str(body["actions"]).lower()

        # Nothing left to find, and the portal login is dead.
        again = client.get("/v1/dsar/search?email=jane@example.com", headers=h).get_json()
        assert again["total_matches"] == 0
        assert client.get("/v1/dsar/search?phone=0801", headers=h).get_json()["total_matches"] == 0
        login = client.post("/v1/vnp/auth/login", json={"email": "jane@example.com", "password": "a real password"})
        assert login.status_code == 401

        from app.modules.wfm.models import CasualWorker
        _as_tenant(db, tid)
        w = db.session.get(CasualWorker, wid)
        assert (w.name, w.phone, w.id_number) == ("[erased]", None, None)

    def test_unsupported_table_aborts_everything(self, app, db, client, seed_tenants, auth_headers):
        tid = seed_tenants["a"]
        cid, _, _ = self._seed(db, tid)
        h = auth_headers("a", permissions=["dsar:manage", "dsar:search"])
        rid = _mk(client, h).get_json()["id"]
        r = client.post(f"/v1/dsar/requests/{rid}/erase", headers=h, json={"records": [
            {"table": "bdc_contacts", "id": str(cid)}, {"table": "users", "id": str(uuid.uuid4())},
        ]})
        assert r.status_code == 400
        # The contact was not touched (request rolled back).
        assert client.get("/v1/dsar/search?email=jane@example.com", headers=h).get_json()["results"].get("bdc_contacts")

    def test_only_erasure_requests_open_requests_and_own_tenant(self, app, db, client, seed_tenants, auth_headers):
        tid = seed_tenants["a"]
        cid, _, _ = self._seed(db, tid)
        h = auth_headers("a", permissions=["dsar:manage"])
        access = _mk(client, h, request_type="access").get_json()["id"]
        rec = {"records": [{"table": "bdc_contacts", "id": str(cid)}]}
        assert client.post(f"/v1/dsar/requests/{access}/erase", headers=h, json=rec).status_code == 400

        erasure = _mk(client, h).get_json()["id"]
        hb = auth_headers("b", permissions=["dsar:manage"])
        rb = _mk(client, hb).get_json()["id"]
        # Tenant B's request cannot erase tenant A's record.
        assert client.post(f"/v1/dsar/requests/{rb}/erase", headers=hb, json=rec).status_code == 404

        client.patch(f"/v1/dsar/requests/{erasure}", headers=h, json={"status": "completed", "resolution_notes": "ok"})
        assert client.post(f"/v1/dsar/requests/{erasure}/erase", headers=h, json=rec).status_code == 409
