"""
Tests for real global search (backend/app/search/) -- RBAC-gated per
entity type, tenant-isolated, real minimum-length guard.
"""
from sqlalchemy import text


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def _seed_searchable_records(db, tenant_id, keyword="Lekki"):
    from app.models.core import Company, Project
    from app.modules.bdc.models import Client
    from app.modules.prc.models import Vendor
    from app.modules.ctm.models import Contract
    import uuid

    _as_tenant(db, tenant_id)
    company = Company(tenant_id=tenant_id, name="Test Co")
    db.session.add(company)
    db.session.flush()

    db.session.add(Project(tenant_id=tenant_id, company_id=company.id, name=f"{keyword} Tower", status="active"))
    db.session.add(Client(tenant_id=tenant_id, name=f"{keyword} Estate Ltd"))
    db.session.add(Vendor(tenant_id=tenant_id, name=f"{keyword} Steel Supply", status="active"))
    db.session.add(Contract(
        tenant_id=tenant_id, tender_id=uuid.uuid4(), contract_number=f"CTR-{keyword}", contract_value=100000, currency="NGN",
    ))
    db.session.commit()


class TestGlobalSearch:
    def test_full_access_caller_sees_all_matching_types(self, app, db, client, seed_tenants, auth_headers):
        _seed_searchable_records(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["*"])

        r = client.get("/v1/search?q=Lekki", headers=headers)
        assert r.status_code == 200
        types = {res["type"] for res in r.get_json()["data"]}
        assert types == {"project", "client", "vendor", "contract"}

    def test_limited_caller_only_sees_permitted_types(self, app, db, client, seed_tenants, auth_headers):
        _seed_searchable_records(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["projects:read"])

        r = client.get("/v1/search?q=Lekki", headers=headers)
        assert r.status_code == 200
        types = {res["type"] for res in r.get_json()["data"]}
        assert types == {"project"}

    def test_caller_with_no_relevant_permissions_sees_nothing(self, app, db, client, seed_tenants, auth_headers):
        _seed_searchable_records(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["hse:read"])

        r = client.get("/v1/search?q=Lekki", headers=headers)
        assert r.status_code == 200
        assert r.get_json()["data"] == []

    def test_query_below_minimum_length_returns_empty_not_an_error(self, app, db, client, seed_tenants, auth_headers):
        _seed_searchable_records(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["*"])

        r = client.get("/v1/search?q=L", headers=headers)
        assert r.status_code == 200
        assert r.get_json()["data"] == []

    def test_no_query_at_all_returns_empty_not_an_error(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        r = client.get("/v1/search", headers=headers)
        assert r.status_code == 200
        assert r.get_json()["data"] == []

    def test_unauthenticated_request_is_rejected(self, app, db, client):
        r = client.get("/v1/search?q=Lekki")
        assert r.status_code == 401

    def test_cross_tenant_isolation(self, app, db, client, seed_tenants, auth_headers):
        _seed_searchable_records(db, seed_tenants["a"], keyword="UniqueTenantAKeyword")
        headers_b = auth_headers("b", permissions=["*"])

        r = client.get("/v1/search?q=UniqueTenantAKeyword", headers=headers_b)
        assert r.status_code == 200
        assert r.get_json()["data"] == []

    def test_soft_deleted_records_are_excluded(self, app, db, client, seed_tenants, auth_headers):
        from app.models.core import Company
        from app.modules.bdc.models import Client
        from datetime import datetime, timezone

        _as_tenant(db, seed_tenants["a"])
        company = Company(tenant_id=seed_tenants["a"], name="Test Co")
        db.session.add(company)
        db.session.flush()
        deleted_client = Client(tenant_id=seed_tenants["a"], name="DeletedSearchTarget Ltd", deleted_at=datetime.now(timezone.utc))
        db.session.add(deleted_client)
        db.session.commit()

        headers = auth_headers("a", permissions=["*"])
        r = client.get("/v1/search?q=DeletedSearchTarget", headers=headers)
        assert r.get_json()["data"] == []
