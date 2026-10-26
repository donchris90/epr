"""DSAR: public intake form, email verification, data export, requester email."""
import uuid

import pytest

from app.models.core import Tenant
from tests.test_dsar import _as_tenant


@pytest.fixture
def sent(monkeypatch):
    from app.notifications import tasks

    out = []
    monkeypatch.setattr(tasks.send_email_notification, "delay", lambda **kw: out.append(kw))
    return out


def _body(**over):
    b = {"request_type": "access", "subject_name": "Jane Doe", "subject_email": "Jane@Example.com", "details": "What do you hold?"}
    b.update(over)
    return b


def _url(tenant_id, tail="/requests"):
    return f"/v1/public/privacy/{tenant_id}{tail}"


def _token_from(email):
    link = [l for l in email["body"].split() if "token=" in l][0]
    return link.split("token=")[1]


class TestPublicIntake:
    def test_form_creates_unverified_public_request_and_emails_link(self, app, db, client, seed_tenants, auth_headers, sent):
        t = seed_tenants["a"]
        r = client.post(_url(t), json=_body())
        assert r.status_code == 201 and r.get_json()["received"] is True
        assert [m["to_address"] for m in sent] == ["jane@example.com"]
        assert f"/privacy-request/{t}/verify?token=" in sent[0]["body"]

        staff = auth_headers("a", permissions=["dsar:manage"])
        rows = client.get("/v1/dsar/requests", headers=staff).get_json()["data"]
        assert len(rows) == 1
        assert rows[0]["source"] == "public" and rows[0]["email_verified"] is False
        assert rows[0]["subject_email"] == "jane@example.com" and rows[0]["status"] == "open"

    def test_verify_marks_email_confirmed_once_and_rejects_bad_token(self, app, db, client, seed_tenants, auth_headers, sent):
        t = seed_tenants["a"]
        client.post(_url(t), json=_body())
        token = _token_from(sent[0])
        assert client.post(_url(t, "/verify"), json={"token": "nope"}).status_code == 400
        assert client.post(_url(t, "/verify"), json={"token": token}).status_code == 200
        assert client.post(_url(t, "/verify"), json={"token": token}).status_code == 200  # idempotent
        staff = auth_headers("a", permissions=["dsar:manage"])
        assert client.get("/v1/dsar/requests", headers=staff).get_json()["data"][0]["email_verified"] is True

    def test_token_from_another_tenant_does_not_verify(self, app, db, client, seed_tenants, sent):
        client.post(_url(seed_tenants["a"]), json=_body())
        token = _token_from(sent[0])
        assert client.post(_url(seed_tenants["b"], "/verify"), json={"token": token}).status_code == 400

    def test_request_lands_only_in_the_named_tenant(self, app, db, client, seed_tenants, auth_headers, sent):
        client.post(_url(seed_tenants["a"]), json=_body())
        other = auth_headers("b", permissions=["dsar:manage"])
        assert client.get("/v1/dsar/requests", headers=other).get_json()["data"] == []

    def test_unknown_or_suspended_tenant_is_404(self, app, db, client, seed_tenants, sent):
        assert client.post(_url(uuid.uuid4()), json=_body()).status_code == 404
        assert client.get(f"/v1/public/privacy/{uuid.uuid4()}").status_code == 404
        t = seed_tenants["a"]
        tenant = db.session.get(Tenant, t)
        tenant.is_suspended = True
        db.session.commit()
        assert client.post(_url(t), json=_body()).status_code == 404

    def test_preview_returns_only_company_name(self, app, db, client, seed_tenants):
        r = client.get(f"/v1/public/privacy/{seed_tenants['a']}")
        assert r.status_code == 200 and set(r.get_json()) == {"company_name", "response_days"}

    def test_validation_and_honeypot(self, app, db, client, seed_tenants, auth_headers, sent):
        t = seed_tenants["a"]
        assert client.post(_url(t), json=_body(subject_email="not-an-email")).status_code == 422
        assert client.post(_url(t), json=_body(request_type="bogus")).status_code == 400
        assert client.post(_url(t), json={"request_type": "access"}).status_code == 422
        assert client.post(_url(t), json=_body(website="http://spam.example")).status_code == 201  # silently dropped
        assert sent == []
        staff = auth_headers("a", permissions=["dsar:manage"])
        assert client.get("/v1/dsar/requests", headers=staff).get_json()["data"] == []

    def test_duplicate_within_a_day_is_not_stored_twice_and_looks_identical(self, app, db, client, seed_tenants, auth_headers, sent):
        t = seed_tenants["a"]
        first = client.post(_url(t), json=_body())
        second = client.post(_url(t), json=_body(subject_email="jane@example.com"))
        assert first.get_json() == second.get_json()
        staff = auth_headers("a", permissions=["dsar:manage"])
        assert len(client.get("/v1/dsar/requests", headers=staff).get_json()["data"]) == 1
        assert len(sent) == 1

    def test_unverified_public_request_blocks_erase_and_export(self, app, db, client, seed_tenants, auth_headers, sent):
        t = seed_tenants["a"]
        client.post(_url(t), json=_body(request_type="erasure"))
        client.post(_url(t), json=_body(request_type="access"))
        staff = auth_headers("a", permissions=["dsar:manage"])
        rows = client.get("/v1/dsar/requests", headers=staff).get_json()["data"]
        by = {r["request_type"]: r["id"] for r in rows}
        assert client.get(f"/v1/dsar/requests/{by['access']}/export", headers=staff).status_code == 409
        r = client.post(f"/v1/dsar/requests/{by['erasure']}/erase", headers=staff,
                        json={"records": [{"table": "bdc_contacts", "id": str(uuid.uuid4())}]})
        assert r.status_code == 409

    def test_public_endpoint_needs_no_login(self, app, db, client, seed_tenants, sent):
        assert client.post(_url(seed_tenants["a"]), json=_body()).status_code == 201


class TestExport:
    def _seed_contact(self, db, tenant_id, email="jane@example.com"):
        from app.modules.bdc.models import Client, Contact

        _as_tenant(db, tenant_id)
        c = Client(tenant_id=tenant_id, name="Acme")
        db.session.add(c)
        db.session.flush()
        contact = Contact(tenant_id=tenant_id, client_id=c.id, name="Jane Doe", email=email, phone="0801", title="QS")
        db.session.add(contact)
        db.session.commit()
        return contact.id

    def test_export_contains_allow_listed_fields_and_is_logged(self, app, db, client, seed_tenants, auth_headers, sent):
        t = seed_tenants["a"]
        cid = self._seed_contact(db, t)
        staff = auth_headers("a", permissions=["dsar:manage"])
        rid = client.post("/v1/dsar/requests", headers=staff, json={"request_type": "access", "subject_name": "Jane", "subject_email": "jane@example.com"}).get_json()["id"]
        r = client.get(f"/v1/dsar/requests/{rid}/export", headers=staff)
        assert r.status_code == 200
        assert "attachment" in r.headers["Content-Disposition"]
        body = r.get_json()
        assert body["total_records"] == 1
        rec = body["records"]["bdc_contacts"][0]
        assert rec["id"] == str(cid) and rec["name"] == "Jane Doe" and rec["phone"] == "0801"
        assert "password" not in str(body).lower()
        got = client.get(f"/v1/dsar/requests/{rid}", headers=staff).get_json()
        assert got["status"] == "in_progress" and got["actions"][-1]["action"] == "exported"
        assert "Jane Doe" not in str(got["actions"])  # log holds no personal data

    def test_export_only_for_access_or_portability_and_open_requests(self, app, db, client, seed_tenants, auth_headers):
        staff = auth_headers("a", permissions=["dsar:manage"])
        mk = lambda t: client.post("/v1/dsar/requests", headers=staff, json={"request_type": t, "subject_name": "J", "subject_email": "j@example.com"}).get_json()["id"]
        assert client.get(f"/v1/dsar/requests/{mk('erasure')}/export", headers=staff).status_code == 400
        rid = mk("portability")
        client.patch(f"/v1/dsar/requests/{rid}", headers=staff, json={"status": "completed", "notify_requester": False})
        assert client.get(f"/v1/dsar/requests/{rid}/export", headers=staff).status_code == 409

    def test_export_requires_manage_and_never_leaks_other_tenants(self, app, db, client, seed_tenants, auth_headers):
        self._seed_contact(db, seed_tenants["b"])
        a = auth_headers("a", permissions=["dsar:manage"])
        rid = client.post("/v1/dsar/requests", headers=a, json={"request_type": "access", "subject_name": "J", "subject_email": "jane@example.com"}).get_json()["id"]
        assert client.get(f"/v1/dsar/requests/{rid}/export", headers=auth_headers("a", permissions=["dsar:search"])).status_code == 403
        assert client.get(f"/v1/dsar/requests/{rid}/export", headers=a).get_json()["total_records"] == 0

    def test_verified_public_request_can_be_exported(self, app, db, client, seed_tenants, auth_headers, sent):
        t = seed_tenants["a"]
        self._seed_contact(db, t)
        client.post(_url(t), json=_body())
        client.post(_url(t, "/verify"), json={"token": _token_from(sent[0])})
        staff = auth_headers("a", permissions=["dsar:manage"])
        rid = client.get("/v1/dsar/requests", headers=staff).get_json()["data"][0]["id"]
        assert client.get(f"/v1/dsar/requests/{rid}/export", headers=staff).get_json()["total_records"] == 1


class TestRequesterNotified:
    def test_completion_emails_the_requester_with_notes(self, app, db, client, seed_tenants, auth_headers, sent):
        staff = auth_headers("a", permissions=["dsar:manage"])
        rid = client.post("/v1/dsar/requests", headers=staff, json={"request_type": "access", "subject_name": "Jane", "subject_email": "jane@example.com"}).get_json()["id"]
        r = client.patch(f"/v1/dsar/requests/{rid}", headers=staff, json={"status": "completed", "resolution_notes": "Copy sent by post"})
        assert r.get_json()["requester_notified_at"] is not None
        assert [m["to_address"] for m in sent] == ["jane@example.com"]
        assert "Copy sent by post" in sent[0]["body"] and "completed" in sent[0]["body"]

    def test_staff_can_opt_out_and_no_email_means_no_send(self, app, db, client, seed_tenants, auth_headers, sent):
        staff = auth_headers("a", permissions=["dsar:manage"])
        r1 = client.post("/v1/dsar/requests", headers=staff, json={"request_type": "access", "subject_name": "A", "subject_email": "a@example.com"}).get_json()["id"]
        r2 = client.post("/v1/dsar/requests", headers=staff, json={"request_type": "access", "subject_name": "B", "subject_phone": "0801"}).get_json()["id"]
        client.patch(f"/v1/dsar/requests/{r1}", headers=staff, json={"status": "completed", "notify_requester": False})
        client.patch(f"/v1/dsar/requests/{r2}", headers=staff, json={"status": "completed"})
        assert sent == []

    def test_unverified_public_requester_does_not_get_staff_notes(self, app, db, client, seed_tenants, auth_headers, sent):
        t = seed_tenants["a"]
        client.post(_url(t), json=_body())
        sent.clear()
        staff = auth_headers("a", permissions=["dsar:manage"])
        rid = client.get("/v1/dsar/requests", headers=staff).get_json()["data"][0]["id"]
        client.patch(f"/v1/dsar/requests/{rid}", headers=staff, json={"status": "rejected", "resolution_notes": "SECRET internal note"})
        assert len(sent) == 1 and "SECRET" not in sent[0]["body"]

    def test_mail_failure_does_not_fail_the_update(self, app, db, client, seed_tenants, auth_headers, monkeypatch):
        from app.notifications import tasks

        def boom(**kw):
            raise RuntimeError("broker down")

        monkeypatch.setattr(tasks.send_email_notification, "delay", boom)
        staff = auth_headers("a", permissions=["dsar:manage"])
        rid = client.post("/v1/dsar/requests", headers=staff, json={"request_type": "access", "subject_name": "A", "subject_email": "a@example.com"}).get_json()["id"]
        r = client.patch(f"/v1/dsar/requests/{rid}", headers=staff, json={"status": "completed"})
        assert r.status_code == 200 and r.get_json()["requester_notified_at"] is None
