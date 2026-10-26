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


class TestStaffListing:
    def _docs(self, db, tid):
        from app.models.core import Document
        from app.modules.prc.models import Vendor
        from app.modules.sub.models import Subcontractor

        _as_tenant(db, tid)
        v1, v2 = Vendor(tenant_id=tid, name="Acme Steel"), Vendor(tenant_id=tid, name="Beta Cement")
        sub = Subcontractor(tenant_id=tid, name="Sparks Electrical")
        db.session.add_all([v1, v2, sub])
        db.session.flush()
        ids = {"v1": v1.id, "v2": v2.id, "sub": sub.id}

        def doc(name, otype=None, oid=None):
            d = Document(tenant_id=tid, file_key=f"k/{name}", original_filename=name, status="uploaded",
                         portal_owner_type=otype, portal_owner_id=oid)
            db.session.add(d)

        doc("staff.pdf")
        doc("acme.pdf", "vnp", v1.id)
        doc("beta.pdf", "vnp", v2.id)
        doc("sparks.pdf", "scp", sub.id)
        db.session.commit()
        return ids

    def _names(self, client, h, qs=""):
        rows = client.get(f"/v1/documents{qs}", headers=h).get_json()["data"]
        return {r["original_filename"]: r for r in rows}

    def test_default_lists_everything_with_source_names(self, app, db, client, seed_tenants, auth_headers):
        self._docs(db, seed_tenants["a"])
        h = auth_headers("a", permissions=["documents:read"])
        rows = self._names(client, h)
        assert set(rows) == {"staff.pdf", "acme.pdf", "beta.pdf", "sparks.pdf"}
        assert rows["acme.pdf"]["source_name"] == "Acme Steel" and rows["acme.pdf"]["portal_owner_type"] == "vnp"
        assert rows["sparks.pdf"]["source_name"] == "Sparks Electrical"
        assert rows["staff.pdf"]["source_name"] is None

    def test_source_filters(self, app, db, client, seed_tenants, auth_headers):
        ids = self._docs(db, seed_tenants["a"])
        h = auth_headers("a", permissions=["documents:read"])
        assert set(self._names(client, h, "?source=staff")) == {"staff.pdf"}
        assert set(self._names(client, h, "?source=vendor")) == {"acme.pdf", "beta.pdf"}
        assert set(self._names(client, h, "?source=subcontractor")) == {"sparks.pdf"}
        assert set(self._names(client, h, f"?source=vendor&portal_owner_id={ids['v1']}")) == {"acme.pdf"}
        assert client.get("/v1/documents?source=bogus", headers=h).status_code == 400

    def test_owner_filter_rejects_a_malformed_id_and_a_foreign_id_returns_nothing(self, app, db, client, seed_tenants, auth_headers):
        import uuid

        self._docs(db, seed_tenants["a"])
        h = auth_headers("a", permissions=["documents:read"])
        assert client.get("/v1/documents?source=vendor&portal_owner_id=not-a-uuid", headers=h).status_code == 400
        assert self._names(client, h, f"?source=vendor&portal_owner_id={uuid.uuid4()}") == {}

    def test_other_tenants_documents_never_listed(self, app, db, client, seed_tenants, auth_headers):
        self._docs(db, seed_tenants["a"])
        h = auth_headers("b", permissions=["documents:read"])
        assert self._names(client, h) == {}


def _scp_with_agreement(db, tid, email="sub@example.com"):
    from app.auth.jwt_utils import hash_password
    from app.modules.scp.models import SubcontractorPortalUser, SubcontractorPortalEmailIndex
    from tests.test_scp import _seed_subcontractor_and_agreement

    sub_id, agreement_id = _seed_subcontractor_and_agreement(db, tid, name=f"Sub {email}")
    _as_tenant(db, tid)
    u = SubcontractorPortalUser(tenant_id=tid, subcontractor_id=sub_id, email=email,
                                password_hash=hash_password("a real password"), is_active=True)
    db.session.add(u)
    db.session.flush()
    uid = u.id
    db.session.add(SubcontractorPortalEmailIndex(email=email, portal_user_id=uid, tenant_id=tid))
    db.session.commit()
    return uid, agreement_id


@pytest.mark.parametrize("portal", ["vnp", "scp"])
class TestPortalDocumentDelete:
    def test_delete_own_document_then_it_is_gone(self, app, db, client, seed_tenants, s3_bucket, portal):
        cfg = PORTALS[portal]
        uid = cfg["seed"](db, seed_tenants["a"])
        h = _login(client, portal, cfg["email"])
        _, doc_id = _upload(client, portal, uid, h)
        url = f"/v1/{portal}/{cfg['base']}/{uid}/documents/{doc_id}"
        assert client.delete(url, headers=h).status_code == 204
        assert client.get(f"/v1/{portal}/{cfg['base']}/{uid}/documents", headers=h).get_json()["data"] == []
        assert client.get(url + "/download", headers=h).status_code == 404

    def test_cannot_delete_another_organisations_document(self, app, db, client, seed_tenants, s3_bucket, portal):
        cfg = PORTALS[portal]
        u1 = cfg["seed"](db, seed_tenants["a"], email="one@example.com")
        u2 = cfg["seed"](db, seed_tenants["a"], email="two@example.com")
        h1, h2 = _login(client, portal, "one@example.com"), _login(client, portal, "two@example.com")
        _, doc_id = _upload(client, portal, u1, h1)
        r = client.delete(f"/v1/{portal}/{cfg['base']}/{u2}/documents/{doc_id}", headers=h2)
        assert r.status_code == 404
        assert len(client.get(f"/v1/{portal}/{cfg['base']}/{u1}/documents", headers=h1).get_json()["data"]) == 1


class TestDeleteBlockedWhileAttached:
    def test_vendor_invoice_attachment_blocks_delete(self, app, db, client, seed_tenants, s3_bucket):
        u = _seed_vnp_user(db, seed_tenants["a"])
        h = _login(client, "vnp", "vendor@example.com")
        _, doc_id = _upload(client, "vnp", u, h, doc_type="invoice")
        po = _po_for_vendor(db, seed_tenants["a"], u)
        r = client.post(f"/v1/vnp/vendor-users/{u}/invoices", headers=h, json={
            "invoice_number": "INV-9", "amount": "10.00", "purchase_order_id": str(po), "invoice_document_id": doc_id})
        assert r.status_code == 201
        d = client.delete(f"/v1/vnp/vendor-users/{u}/documents/{doc_id}", headers=h)
        assert d.status_code == 409
        assert len(client.get(f"/v1/vnp/vendor-users/{u}/documents", headers=h).get_json()["data"]) == 1


class TestClaimSupportingDocument:
    def _claim(self, client, h, uid, agreement_id, doc_id=None):
        body = {"agreement_id": str(agreement_id), "claim_type": "delay", "description": "Access blocked", "claimed_days": 3}
        if doc_id:
            body["supporting_document_id"] = doc_id
        return client.post(f"/v1/scp/portal-users/{uid}/claims", headers=h, json=body)

    def test_claim_can_carry_own_uploaded_document_and_it_blocks_delete(self, app, db, client, seed_tenants, s3_bucket):
        uid, agreement_id = _scp_with_agreement(db, seed_tenants["a"])
        h = _login(client, "scp", "sub@example.com")
        _, doc_id = _upload(client, "scp", uid, h, doc_type="other")
        r = self._claim(client, h, uid, agreement_id, doc_id)
        assert r.status_code == 201
        assert r.get_json()["supporting_document_id"] == doc_id
        listed = client.get(f"/v1/scp/portal-users/{uid}/claims?agreement_id={agreement_id}", headers=h).get_json()["data"]
        assert listed[0]["supporting_document_id"] == doc_id
        assert client.delete(f"/v1/scp/portal-users/{uid}/documents/{doc_id}", headers=h).status_code == 409

    def test_staff_claim_list_exposes_the_evidence_id(self, app, db, client, seed_tenants, s3_bucket, auth_headers):
        uid, agreement_id = _scp_with_agreement(db, seed_tenants["a"])
        h = _login(client, "scp", "sub@example.com")
        _, doc_id = _upload(client, "scp", uid, h, doc_type="other")
        assert self._claim(client, h, uid, agreement_id, doc_id).status_code == 201
        staff = auth_headers("a", permissions=["sub:read", "documents:read"])
        rows = client.get(f"/v1/sub/agreements/{agreement_id}/claims", headers=staff).get_json()["data"]
        assert rows[0]["supporting_document_id"] == doc_id
        # ...and staff can resolve it to a download link through the library API
        d = client.get(f"/v1/documents/{doc_id}", headers=staff)
        assert d.status_code == 200 and d.get_json().get("download_url")

    def test_claim_without_document_still_works(self, app, db, client, seed_tenants, s3_bucket):
        uid, agreement_id = _scp_with_agreement(db, seed_tenants["a"])
        h = _login(client, "scp", "sub@example.com")
        r = self._claim(client, h, uid, agreement_id)
        assert r.status_code == 201 and r.get_json()["supporting_document_id"] is None

    def test_claim_cannot_use_another_organisations_or_a_pending_document(self, app, db, client, seed_tenants, s3_bucket):
        u1, a1 = _scp_with_agreement(db, seed_tenants["a"], "one@example.com")
        u2, _ = _scp_with_agreement(db, seed_tenants["a"], "two@example.com")
        h1, h2 = _login(client, "scp", "one@example.com"), _login(client, "scp", "two@example.com")
        _, theirs = _upload(client, "scp", u2, h2, doc_type="other")
        assert self._claim(client, h1, u1, a1, theirs).status_code == 404

        pending = client.post(f"/v1/scp/portal-users/{u1}/documents/upload-request", headers=h1, json={
            "original_filename": "a.pdf", "content_type": "application/pdf", "doc_type": "other"}).get_json()["id"]
        assert self._claim(client, h1, u1, a1, pending).status_code == 409
