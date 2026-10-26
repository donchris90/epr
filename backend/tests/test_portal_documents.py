"""Portal document upload / list / download, scoped to the owning organisation."""
import uuid

import pytest
import requests
from moto import mock_aws
from sqlalchemy import text

from tests.test_documents import s3_bucket  # noqa: F401  (fixture)
from tests.test_scp_vnp_portal_auth import _seed_scp_user, _seed_vnp_user


def _as_tenant(db, tid):
    db.session.execute(text("SET LOCAL app.tenant_id = :t"), {"t": str(tid)})


def _login(client, portal, email):
    r = client.post(f"/v1/{portal}/auth/login", json={"email": email, "password": "a real password"})
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


PORTALS = {
    "vnp": dict(seed=_seed_vnp_user, email="vendor@example.com", base="vendor-users", doc_type="trade_license"),
    "scp": dict(seed=_seed_scp_user, email="sub@example.com", base="portal-users", doc_type="insurance"),
}


def _upload(client, portal, uid, headers, *, filename="licence.pdf", ctype="application/pdf", doc_type=None, body=b"%PDF real bytes"):
    cfg = PORTALS[portal]
    r = client.post(
        f"/v1/{portal}/{cfg['base']}/{uid}/documents/upload-request",
        json={"original_filename": filename, "content_type": ctype, "doc_type": doc_type or cfg["doc_type"]},
        headers=headers,
    )
    if r.status_code != 201:
        return r, None
    j = r.get_json()
    assert requests.put(j["upload_url"], data=body, headers={"Content-Type": ctype}).status_code == 200
    c = client.post(f"/v1/{portal}/{cfg['base']}/{uid}/documents/{j['id']}/confirm", headers=headers)
    return c, j["id"]


@pytest.mark.parametrize("portal", ["vnp", "scp"])
class TestPortalDocuments:
    def test_upload_confirm_list_download_roundtrip(self, app, db, client, seed_tenants, s3_bucket, portal):
        cfg = PORTALS[portal]
        uid = cfg["seed"](db, seed_tenants["a"])
        h = _login(client, portal, cfg["email"])
        r, doc_id = _upload(client, portal, uid, h, body=b"hello portal")
        assert r.status_code == 200 and r.get_json()["status"] == "uploaded"
        assert r.get_json()["size_bytes"] == len(b"hello portal")

        rows = client.get(f"/v1/{portal}/{cfg['base']}/{uid}/documents", headers=h).get_json()["data"]
        assert [d["id"] for d in rows] == [doc_id]
        url = client.get(f"/v1/{portal}/{cfg['base']}/{uid}/documents/{doc_id}/download", headers=h).get_json()["download_url"]
        assert requests.get(url).content == b"hello portal"

    def test_disallowed_type_and_unknown_doc_type_rejected(self, app, db, client, seed_tenants, s3_bucket, portal):
        cfg = PORTALS[portal]
        uid = cfg["seed"](db, seed_tenants["a"])
        h = _login(client, portal, cfg["email"])
        r, _ = _upload(client, portal, uid, h, filename="x.exe", ctype="application/x-msdownload")
        assert r.status_code == 400
        r, _ = _upload(client, portal, uid, h, doc_type="nonsense")
        assert r.status_code == 400

    def test_oversize_upload_is_rejected_and_removed(self, app, db, client, seed_tenants, s3_bucket, portal, monkeypatch):
        from app.documents import portal as doc_portal

        monkeypatch.setattr(doc_portal, "MAX_BYTES", 5)
        cfg = PORTALS[portal]
        uid = cfg["seed"](db, seed_tenants["a"])
        h = _login(client, portal, cfg["email"])
        r, _ = _upload(client, portal, uid, h, body=b"way more than five bytes")
        assert r.status_code == 413
        assert client.get(f"/v1/{portal}/{cfg['base']}/{uid}/documents", headers=h).get_json()["data"] == []

    def test_pending_uploads_are_not_listed(self, app, db, client, seed_tenants, s3_bucket, portal):
        cfg = PORTALS[portal]
        uid = cfg["seed"](db, seed_tenants["a"])
        h = _login(client, portal, cfg["email"])
        client.post(
            f"/v1/{portal}/{cfg['base']}/{uid}/documents/upload-request",
            json={"original_filename": "a.pdf", "content_type": "application/pdf", "doc_type": cfg["doc_type"]},
            headers=h,
        )
        assert client.get(f"/v1/{portal}/{cfg['base']}/{uid}/documents", headers=h).get_json()["data"] == []

    def test_other_organisation_cannot_see_or_download(self, app, db, client, seed_tenants, s3_bucket, portal):
        cfg = PORTALS[portal]
        u1 = cfg["seed"](db, seed_tenants["a"], email="one@example.com")
        u2 = cfg["seed"](db, seed_tenants["a"], email="two@example.com")  # different org (random org id)
        h1, h2 = _login(client, portal, "one@example.com"), _login(client, portal, "two@example.com")
        _, doc_id = _upload(client, portal, u1, h1)

        assert client.get(f"/v1/{portal}/{cfg['base']}/{u2}/documents", headers=h2).get_json()["data"] == []
        r = client.get(f"/v1/{portal}/{cfg['base']}/{u2}/documents/{doc_id}/download", headers=h2)
        assert r.status_code == 404
        r = client.post(f"/v1/{portal}/{cfg['base']}/{u2}/documents/{doc_id}/confirm", headers=h2)
        assert r.status_code == 404
        # and cannot act as the other user
        assert client.get(f"/v1/{portal}/{cfg['base']}/{u1}/documents", headers=h2).status_code == 403

    def test_staff_documents_are_not_visible_to_portal(self, app, db, client, seed_tenants, s3_bucket, portal, auth_headers):
        cfg = PORTALS[portal]
        uid = cfg["seed"](db, seed_tenants["a"])
        h = _login(client, portal, cfg["email"])
        staff = auth_headers("a", permissions=["documents:write"])
        r = client.post("/v1/documents/upload-request", json={"original_filename": "s.pdf", "content_type": "application/pdf"}, headers=staff)
        staff_id = r.get_json()["id"]
        r = client.get(f"/v1/{portal}/{cfg['base']}/{uid}/documents/{staff_id}/download", headers=h)
        assert r.status_code == 404

    def test_portal_token_cannot_use_staff_documents_api(self, app, db, client, seed_tenants, portal):
        cfg = PORTALS[portal]
        cfg["seed"](db, seed_tenants["a"])
        h = _login(client, portal, cfg["email"])
        assert client.get("/v1/documents", headers=h).status_code == 403


class TestInvoiceAttachment:
    def test_vendor_can_attach_own_uploaded_document_but_not_anothers(self, app, db, client, seed_tenants, s3_bucket):
        cfg = PORTALS["vnp"]
        u1 = _seed_vnp_user(db, seed_tenants["a"], email="one@example.com")
        u2 = _seed_vnp_user(db, seed_tenants["a"], email="two@example.com")
        h1, h2 = _login(client, "vnp", "one@example.com"), _login(client, "vnp", "two@example.com")
        _, mine = _upload(client, "vnp", u1, h1, doc_type="invoice")
        _, theirs = _upload(client, "vnp", u2, h2, doc_type="invoice")

        po = _po_for_vendor(db, seed_tenants["a"], u1)
        body = {"invoice_number": "INV-1", "amount": "100.00", "purchase_order_id": str(po)}
        ok = client.post(f"/v1/vnp/vendor-users/{u1}/invoices", json={**body, "invoice_document_id": mine}, headers=h1)
        assert ok.status_code == 201
        bad = client.post(f"/v1/vnp/vendor-users/{u1}/invoices", json={**body, "invoice_number": "INV-2", "invoice_document_id": theirs}, headers=h1)
        assert bad.status_code == 404


def _po_for_vendor(db, tid, vendor_user_id):
    from app.modules.prc.models import PurchaseOrder, Vendor
    from app.modules.vnp.models import VendorPortalUser

    _as_tenant(db, tid)
    vendor_id = db.session.get(VendorPortalUser, vendor_user_id).vendor_id
    db.session.add(Vendor(id=vendor_id, tenant_id=tid, name="Test vendor"))
    db.session.flush()
    po = PurchaseOrder(tenant_id=tid, vendor_id=vendor_id, po_number=f"PO-{uuid.uuid4().hex[:6]}", total_value=1000, currency="NGN")
    db.session.add(po)
    db.session.flush()
    pid = po.id
    db.session.commit()
    return pid
