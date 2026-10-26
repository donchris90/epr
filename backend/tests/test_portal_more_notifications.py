"""PO issued / progress verified / retention released portal notifications,
and the email copy of the finance banking-change alert."""
import pytest

from tests.test_portal_notifications import _as_tenant, _login, _scp_user, _vnp_user
from tests.test_scp import _seed_subcontractor_and_agreement
from tests.test_vnp_banking_review import TestFinanceAlert


@pytest.fixture
def sent(monkeypatch):
    from app.notifications import tasks

    out = []
    monkeypatch.setattr(tasks.send_email_notification, "delay", lambda **kw: out.append(kw))
    return out


def _inbox(client, portal, email):
    return client.get("/v1/notifications", headers=_login(client, portal, email)).get_json()["data"]


class TestPoIssued:
    def _po(self, db, tid, vendor_name="Acme Steel", status="approved", number="PO-77"):
        from app.modules.prc.models import PurchaseOrder, Vendor

        _as_tenant(db, tid)
        v = Vendor(tenant_id=tid, name=vendor_name)
        db.session.add(v)
        db.session.flush()
        po = PurchaseOrder(tenant_id=tid, vendor_id=v.id, po_number=number, status=status, total_value=1000)
        db.session.add(po)
        db.session.flush()
        ids = (v.id, po.id)
        db.session.commit()
        return ids

    def test_issuing_notifies_only_that_vendors_active_users(self, app, db, client, seed_tenants, auth_headers):
        t = seed_tenants["a"]
        vid, po_id = self._po(db, t)
        other_vid, _ = self._po(db, t, vendor_name="Other Ltd", number="PO-78")
        _vnp_user(db, t, vid, "one@acme.com")
        _vnp_user(db, t, other_vid, "x@other.com")
        r = client.post(f"/v1/prc/purchase-orders/{po_id}/issue", headers=auth_headers("a"), json={})
        assert r.status_code == 200
        items = _inbox(client, "vnp", "one@acme.com")
        assert [i["type"] for i in items] == ["vnp.po_issued"]
        assert "PO-77" in items[0]["title"]
        assert items[0]["data"] == {"entity_type": "purchase_order", "entity_id": str(po_id)}
        assert _inbox(client, "vnp", "x@other.com") == []

    def test_blocked_issue_sends_nothing(self, app, db, client, seed_tenants, auth_headers):
        t = seed_tenants["a"]
        vid, po_id = self._po(db, t, status="draft")
        _vnp_user(db, t, vid, "one@acme.com")
        assert client.post(f"/v1/prc/purchase-orders/{po_id}/issue", headers=auth_headers("a"), json={}).status_code == 409
        assert _inbox(client, "vnp", "one@acme.com") == []


class TestProgressAndRetention:
    def _setup(self, db, client, tid, auth_headers):
        sub_id, agr_id = _seed_subcontractor_and_agreement(db, tid)
        other_sub, _ = _seed_subcontractor_and_agreement(db, tid, name="Other Sub")
        _scp_user(db, tid, sub_id, "me@sub.com")
        _scp_user(db, tid, other_sub, "them@sub.com")
        h = auth_headers("a", permissions=["*"])
        scope = client.post(f"/v1/sub/agreements/{agr_id}/scope-items", headers=h, json={"description": "Wiring", "is_lump_sum": True, "lump_sum_amount": "100000"}).get_json()["id"]
        sheet = client.post("/v1/sub/measurement-sheets", headers=h, json={"agreement_id": str(agr_id), "scope_item_id": scope, "verified_quantity": "100"}).get_json()["id"]
        return agr_id, sheet, h

    def test_verifying_a_measurement_notifies_the_subcontractor(self, app, db, client, seed_tenants, auth_headers):
        agr_id, sheet, h = self._setup(db, client, seed_tenants["a"], auth_headers)
        assert client.post(f"/v1/sub/measurement-sheets/{sheet}/verify", headers=h).status_code == 200
        items = _inbox(client, "scp", "me@sub.com")
        assert [i["type"] for i in items] == ["scp.progress_verified"]
        assert items[0]["body"] == "Verified quantity: 100"
        assert items[0]["data"]["agreement_id"] == str(agr_id)
        assert _inbox(client, "scp", "them@sub.com") == []

    def test_second_verify_is_refused_and_does_not_notify_again(self, app, db, client, seed_tenants, auth_headers):
        _, sheet, h = self._setup(db, client, seed_tenants["a"], auth_headers)
        client.post(f"/v1/sub/measurement-sheets/{sheet}/verify", headers=h)
        assert client.post(f"/v1/sub/measurement-sheets/{sheet}/verify", headers=h).status_code == 409
        assert len(_inbox(client, "scp", "me@sub.com")) == 1

    def test_retention_release_notifies_per_stage(self, app, db, client, seed_tenants, auth_headers):
        agr_id, _, h = self._setup(db, client, seed_tenants["a"], auth_headers)
        ret = client.post(f"/v1/sub/agreements/{agr_id}/retention", headers=h, json={"percentage": "5"}).get_json()["id"]
        assert client.post(f"/v1/sub/retention/{ret}/release", headers=h, json={"stage": "final"}).status_code == 409
        assert _inbox(client, "scp", "me@sub.com") == []  # refused release notifies nobody
        assert client.post(f"/v1/sub/retention/{ret}/release", headers=h, json={"stage": "substantial_completion"}).status_code == 200
        assert client.post(f"/v1/sub/retention/{ret}/release", headers=h, json={"stage": "final"}).status_code == 200
        titles = [i["title"] for i in _inbox(client, "scp", "me@sub.com")]
        assert sorted(t.split(" retention")[0] for t in titles) == ["Final", "Substantial completion"]
        assert _inbox(client, "scp", "them@sub.com") == []


class TestBankingAlertEmail:
    def test_finance_approvers_are_emailed_as_well(self, app, db, client, seed_tenants, auth_headers, sent):
        t = seed_tenants["a"]
        helper = TestFinanceAlert()
        helper._staff(db, t, "fin@x.com", ["vnp:finance_approve"])
        helper._staff(db, t, "pm@x.com", ["prc:read"])
        helper._staff(db, t, "gone@x.com", ["vnp:finance_approve"], status="removed")
        assert helper._submit(client, db, t).status_code == 201
        assert [m["to_address"] for m in sent] == ["fin@x.com"]
        assert "Acme Steel" in sent[0]["subject"]

    def test_a_user_who_switched_email_off_for_finance_is_not_emailed(self, app, db, client, seed_tenants, sent):
        from app.notifications.services import set_preferences

        t = seed_tenants["a"]
        helper = TestFinanceAlert()
        uid = helper._staff(db, t, "fin@x.com", ["vnp:finance_approve"])
        _as_tenant(db, t)
        set_preferences(t, user_id=uid, items=[{"category": "finance", "in_app": True, "email": False}])
        assert helper._submit(client, db, t).status_code == 201
        assert sent == []

    def test_mail_failure_does_not_fail_the_submission(self, app, db, client, seed_tenants, monkeypatch):
        from app.notifications import tasks

        def boom(**kw):
            raise RuntimeError("broker down")

        monkeypatch.setattr(tasks.send_email_notification, "delay", boom)
        t = seed_tenants["a"]
        helper = TestFinanceAlert()
        helper._staff(db, t, "fin@x.com", ["vnp:finance_approve"])
        assert helper._submit(client, db, t).status_code == 201
