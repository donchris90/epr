"""
Tests for the Subcontractor Portal (Module 27, app/modules/scp/).
"""
import uuid

from sqlalchemy import text


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def _seed_subcontractor_and_agreement(db, tenant_id, *, name="Test Sub Co"):
    from app.modules.sub.models import Subcontractor, SubcontractAgreement

    _as_tenant(db, tenant_id)
    subcontractor = Subcontractor(tenant_id=tenant_id, name=name, trade_specialty="electrical")
    db.session.add(subcontractor)
    db.session.flush()

    # agreement_number is unique per tenant (uq_sub_agreements_tenant_number,
    # a real constraint found by actually running this against Postgres) --
    # suffixed with the subcontractor's own id so seeding two subcontractors
    # in the same test/tenant never collides.
    agreement = SubcontractAgreement(
        tenant_id=tenant_id, subcontractor_id=subcontractor.id,
        agreement_number=f"SC-TEST-{subcontractor.id}", value=500000,
    )
    db.session.add(agreement)
    db.session.flush()

    # Captured as plain values before commit -- expire_on_commit means
    # touching these ORM objects' attributes after commit triggers a
    # re-SELECT with no tenant context set, the same pitfall
    # documented throughout this codebase's other services/tests.
    result = (subcontractor.id, agreement.id)
    db.session.commit()
    return result


class TestSubcontractorPortal:
    def test_create_portal_user(self, app, db, client, seed_tenants, auth_headers):
        subcontractor_id, _ = _seed_subcontractor_and_agreement(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["scp:approve"])

        r = client.post(
            "/v1/scp/portal-users", headers=headers,
            json={"subcontractor_id": str(subcontractor_id), "email": "rep@testsub.com", "password": "a real password"},
        )
        assert r.status_code == 201
        assert r.get_json()["subcontractor_id"] == str(subcontractor_id)

    def test_submit_progress_against_own_agreement(self, app, db, client, seed_tenants, auth_headers):
        subcontractor_id, agreement_id = _seed_subcontractor_and_agreement(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["scp:approve", "scp:write"])

        portal_user_id = client.post(
            "/v1/scp/portal-users", headers=headers,
            json={"subcontractor_id": str(subcontractor_id), "email": "rep@testsub.com", "password": "a real password"},
        ).get_json()["id"]

        r = client.post(
            f"/v1/scp/portal-users/{portal_user_id}/progress-entries", headers=headers,
            json={"agreement_id": str(agreement_id), "submitted_quantity": "150.0"},
        )
        assert r.status_code == 201
        assert r.get_json()["status"] == "submitted"
        assert r.get_json()["submitted_quantity"] == "150.0000"

    def test_cannot_submit_progress_against_another_subcontractors_agreement(self, app, db, client, seed_tenants, auth_headers):
        sub_a_id, agreement_a_id = _seed_subcontractor_and_agreement(db, seed_tenants["a"], name="Sub A")
        sub_b_id, _ = _seed_subcontractor_and_agreement(db, seed_tenants["a"], name="Sub B")
        headers = auth_headers("a", permissions=["scp:approve", "scp:write"])

        portal_user_b_id = client.post(
            "/v1/scp/portal-users", headers=headers,
            json={"subcontractor_id": str(sub_b_id), "email": "rep@subb.com", "password": "a real password"},
        ).get_json()["id"]

        r = client.post(
            f"/v1/scp/portal-users/{portal_user_b_id}/progress-entries", headers=headers,
            json={"agreement_id": str(agreement_a_id), "submitted_quantity": "999"},
        )
        assert r.status_code == 403

    def test_view_own_payment_certificates(self, app, db, client, seed_tenants, auth_headers):
        subcontractor_id, agreement_id = _seed_subcontractor_and_agreement(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["scp:approve", "scp:read"])

        _as_tenant(db, seed_tenants["a"])
        from app.modules.sub.models import PaymentCertificate
        cert = PaymentCertificate(
            tenant_id=seed_tenants["a"], agreement_id=agreement_id, certificate_number="PC-TEST-001",
            gross_certified_amount=100000, net_payable=95000, status="issued",
        )
        db.session.add(cert)
        db.session.commit()

        portal_user_id = client.post(
            "/v1/scp/portal-users", headers=headers,
            json={"subcontractor_id": str(subcontractor_id), "email": "rep@testsub.com", "password": "a real password"},
        ).get_json()["id"]

        r = client.get(
            f"/v1/scp/portal-users/{portal_user_id}/payment-certificates?agreement_id={agreement_id}", headers=headers
        )
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1
        assert r.get_json()["data"][0]["certificate_number"] == "PC-TEST-001"

    def test_cannot_view_another_subcontractors_payment_certificates(self, app, db, client, seed_tenants, auth_headers):
        sub_a_id, agreement_a_id = _seed_subcontractor_and_agreement(db, seed_tenants["a"], name="Sub A")
        sub_b_id, _ = _seed_subcontractor_and_agreement(db, seed_tenants["a"], name="Sub B")
        headers = auth_headers("a", permissions=["scp:approve", "scp:read"])

        portal_user_b_id = client.post(
            "/v1/scp/portal-users", headers=headers,
            json={"subcontractor_id": str(sub_b_id), "email": "rep@subb.com", "password": "a real password"},
        ).get_json()["id"]

        r = client.get(
            f"/v1/scp/portal-users/{portal_user_b_id}/payment-certificates?agreement_id={agreement_a_id}", headers=headers
        )
        assert r.status_code == 403

    def test_submit_claim(self, app, db, client, seed_tenants, auth_headers):
        subcontractor_id, agreement_id = _seed_subcontractor_and_agreement(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["scp:approve", "scp:write"])

        portal_user_id = client.post(
            "/v1/scp/portal-users", headers=headers,
            json={"subcontractor_id": str(subcontractor_id), "email": "rep@testsub.com", "password": "a real password"},
        ).get_json()["id"]

        r = client.post(
            f"/v1/scp/portal-users/{portal_user_id}/claims", headers=headers,
            json={
                "agreement_id": str(agreement_id), "claim_type": "delay",
                "description": "Site access blocked", "claimed_days": 5,
            },
        )
        assert r.status_code == 201
        assert r.get_json()["status"] == "submitted"
        assert r.get_json()["claim_type"] == "delay"

    def test_invalid_claim_type_rejected(self, app, db, client, seed_tenants, auth_headers):
        subcontractor_id, agreement_id = _seed_subcontractor_and_agreement(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["scp:approve", "scp:write"])

        portal_user_id = client.post(
            "/v1/scp/portal-users", headers=headers,
            json={"subcontractor_id": str(subcontractor_id), "email": "rep@testsub.com", "password": "a real password"},
        ).get_json()["id"]

        r = client.post(
            f"/v1/scp/portal-users/{portal_user_id}/claims", headers=headers,
            json={"agreement_id": str(agreement_id), "claim_type": "not_a_real_type", "description": "x"},
        )
        assert r.status_code == 422

    def test_cross_tenant_isolation(self, app, db, client, seed_tenants, auth_headers):
        sub_a_id, _ = _seed_subcontractor_and_agreement(db, seed_tenants["a"])
        headers_a = auth_headers("a", permissions=["scp:approve", "scp:read"])
        headers_b = auth_headers("b", permissions=["scp:approve", "scp:read"])

        portal_user_id = client.post(
            "/v1/scp/portal-users", headers=headers_a,
            json={"subcontractor_id": str(sub_a_id), "email": "rep@testsub.com", "password": "a real password"},
        ).get_json()["id"]

        r = client.get(f"/v1/scp/portal-users/{portal_user_id}/progress-entries?agreement_id={uuid.uuid4()}", headers=headers_b)
        assert r.status_code == 404

    def test_creating_portal_user_requires_scp_approve_permission(self, app, db, client, seed_tenants, auth_headers):
        subcontractor_id, _ = _seed_subcontractor_and_agreement(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["scp:write"])  # write, not approve

        r = client.post(
            "/v1/scp/portal-users", headers=headers,
            json={"subcontractor_id": str(subcontractor_id), "email": "rep@testsub.com", "password": "a real password"},
        )
        assert r.status_code == 403
