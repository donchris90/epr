"""
Tests for app/dsar/ -- the cross-module "find every record about this
person" search that fulfilling a real Data Subject Access Request
would otherwise require a human to do by hand, table by table.
"""
from sqlalchemy import text


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def _seed_matching_records(db, tenant_id, *, email, phone):
    from app.models.core import User
    from app.auth.jwt_utils import hash_password
    from app.modules.bdc.models import Contact
    from app.modules.wfm.models import CasualWorker
    from app.modules.clp.models import ClientPortalUser

    _as_tenant(db, tenant_id)
    db.session.add(User(tenant_id=tenant_id, email=email, password_hash=hash_password("x"), status="active"))
    db.session.add(Contact(tenant_id=tenant_id, name="Jane Doe", email=email, phone=phone))
    db.session.add(CasualWorker(tenant_id=tenant_id, name="Jane Doe", phone=phone))
    db.session.add(ClientPortalUser(tenant_id=tenant_id, client_organization_name="Acme Co", email=email))
    # A deliberately unrelated record that must never match.
    db.session.add(Contact(tenant_id=tenant_id, name="Someone Else", email="unrelated@example.com"))
    db.session.commit()


class TestDSARSearch:
    def test_finds_matching_records_by_email_across_modules(self, app, db, client, seed_tenants, auth_headers):
        email, phone = "jane.doe@example.com", "08012345678"
        _seed_matching_records(db, seed_tenants["a"], email=email, phone=phone)

        r = client.get(f"/v1/dsar/search?email={email}", headers=auth_headers("a"))

        assert r.status_code == 200
        body = r.get_json()
        # Matches by email: users, bdc_contacts, clp_portal_users --
        # NOT wfm_casual_workers, which has no email field at all.
        assert body["total_matches"] == 3
        assert set(body["results"].keys()) == {"users", "bdc_contacts", "clp_portal_users"}

    def test_finds_matching_records_by_phone_across_modules(self, app, db, client, seed_tenants, auth_headers):
        email, phone = "jane.doe@example.com", "08012345678"
        _seed_matching_records(db, seed_tenants["a"], email=email, phone=phone)

        r = client.get(f"/v1/dsar/search?phone={phone}", headers=auth_headers("a"))

        assert r.status_code == 200
        body = r.get_json()
        # Matches by phone: bdc_contacts, wfm_casual_workers only.
        assert body["total_matches"] == 2
        assert set(body["results"].keys()) == {"bdc_contacts", "wfm_casual_workers"}

    def test_does_not_leak_matching_records_from_another_tenant(self, app, db, client, seed_tenants, auth_headers):
        email = "shared@example.com"
        from app.modules.bdc.models import Contact

        _as_tenant(db, seed_tenants["a"])
        db.session.add(Contact(tenant_id=seed_tenants["a"], name="Tenant A's Jane", email=email))
        db.session.commit()

        _as_tenant(db, seed_tenants["b"])
        db.session.add(Contact(tenant_id=seed_tenants["b"], name="Tenant B's Jane", email=email))
        db.session.commit()

        r = client.get(f"/v1/dsar/search?email={email}", headers=auth_headers("a"))

        body = r.get_json()
        assert body["total_matches"] == 1
        assert "Tenant A's Jane" in body["results"]["bdc_contacts"][0]["summary"]

    def test_requires_dsar_search_permission_specifically(self, app, db, client, seed_tenants, auth_headers):
        r = client.get(
            "/v1/dsar/search?email=jane@example.com",
            headers=auth_headers("a", permissions=["some:other_permission"]),
        )
        assert r.status_code == 403

    def test_requires_at_least_one_query_parameter(self, app, db, client, seed_tenants, auth_headers):
        r = client.get("/v1/dsar/search", headers=auth_headers("a"))
        assert r.status_code == 400

    def test_email_match_is_case_insensitive(self, app, db, client, seed_tenants, auth_headers):
        from app.modules.bdc.models import Contact

        _as_tenant(db, seed_tenants["a"])
        db.session.add(Contact(tenant_id=seed_tenants["a"], name="Jane Doe", email="Jane.Doe@Example.COM"))
        db.session.commit()

        r = client.get("/v1/dsar/search?email=jane.doe@example.com", headers=auth_headers("a"))

        assert r.get_json()["total_matches"] == 1
