"""
Tests for real Project CRUD (backend/app/projects/) -- create, real
detail (including a genuine, not-fabricated contract value lookup),
update, and cross-tenant isolation.
"""
import uuid
from decimal import Decimal

from sqlalchemy import text


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def _seed_company_client_pm(db, tenant_id):
    from app.models.core import Company, User
    from app.modules.bdc.models import Client
    from app.auth.jwt_utils import hash_password

    _as_tenant(db, tenant_id)
    company = Company(tenant_id=tenant_id, name="Test Co")
    client_row = Client(tenant_id=tenant_id, name="Test Client Ltd")
    pm = User(tenant_id=tenant_id, email=f"pm-{uuid.uuid4().hex[:8]}@example.com", password_hash=hash_password("x"), status="active")
    db.session.add_all([company, client_row, pm])
    db.session.flush()
    # Captured as plain values before the commit below, not accessed
    # on the ORM objects afterward -- expire_on_commit means any later
    # attribute access on these objects can trigger a fresh SELECT
    # needing tenant context that may no longer be set by then.
    ids = {"company_id": str(company.id), "client_id": str(client_row.id), "pm_id": str(pm.id)}
    db.session.commit()
    return ids


class TestCreateProject:
    def test_creates_a_real_project_with_all_fields(self, app, db, client, seed_tenants, auth_headers):
        ids = _seed_company_client_pm(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["projects:manage"])

        r = client.post("/v1/projects", headers=headers, json={
            "company_id": ids["company_id"], "name": "Lekki Tower", "client_id": ids["client_id"],
            "project_manager_id": ids["pm_id"], "start_date": "2026-01-15", "end_date": "2027-06-30",
        })
        assert r.status_code == 201
        assert r.get_json()["name"] == "Lekki Tower"
        assert r.get_json()["client_id"] == ids["client_id"]

    def test_creates_a_minimal_project_with_only_required_fields(self, app, db, client, seed_tenants, auth_headers):
        ids = _seed_company_client_pm(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["projects:manage"])

        r = client.post("/v1/projects", headers=headers, json={"company_id": ids["company_id"], "name": "Minimal Project"})
        assert r.status_code == 201
        assert r.get_json()["client_id"] is None

    def test_rejects_a_client_id_that_does_not_exist(self, app, db, client, seed_tenants, auth_headers):
        ids = _seed_company_client_pm(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["projects:manage"])

        r = client.post("/v1/projects", headers=headers, json={
            "company_id": ids["company_id"], "name": "Bad Project", "client_id": str(uuid.uuid4()),
        })
        assert r.status_code == 404

    def test_requires_the_manage_permission_not_just_read(self, app, db, client, seed_tenants, auth_headers):
        ids = _seed_company_client_pm(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["projects:read"])

        r = client.post("/v1/projects", headers=headers, json={"company_id": ids["company_id"], "name": "Should Fail"})
        assert r.status_code == 403


class TestGetProjectDetail:
    def test_detail_includes_real_client_name(self, app, db, client, seed_tenants, auth_headers):
        ids = _seed_company_client_pm(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["projects:manage", "projects:read"])

        r = client.post("/v1/projects", headers=headers, json={"company_id": ids["company_id"], "name": "P1", "client_id": ids["client_id"]})
        project_id = r.get_json()["id"]

        r2 = client.get(f"/v1/projects/{project_id}", headers=headers)
        assert r2.status_code == 200
        assert r2.get_json()["client_name"] == "Test Client Ltd"

    def test_no_contract_means_no_contract_value_not_a_fabricated_one(self, app, db, client, seed_tenants, auth_headers):
        ids = _seed_company_client_pm(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["projects:manage", "projects:read"])

        r = client.post("/v1/projects", headers=headers, json={"company_id": ids["company_id"], "name": "No Contract Yet"})
        project_id = r.get_json()["id"]

        r2 = client.get(f"/v1/projects/{project_id}", headers=headers)
        assert r2.get_json()["contract_value"] is None
        assert r2.get_json()["currency"] is None

    def test_real_linked_contract_value_is_reflected_honestly(self, app, db, client, seed_tenants, auth_headers):
        from app.modules.ctm.models import Contract

        ids = _seed_company_client_pm(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["projects:manage", "projects:read"])

        r = client.post("/v1/projects", headers=headers, json={"company_id": ids["company_id"], "name": "With Contract"})
        project_id = r.get_json()["id"]

        _as_tenant(db, seed_tenants["a"])
        db.session.add(Contract(
            tenant_id=seed_tenants["a"], tender_id=uuid.uuid4(), project_id=project_id,
            contract_number="CTR-01", contract_value=Decimal("450000000"), currency="NGN",
        ))
        db.session.commit()

        r2 = client.get(f"/v1/projects/{project_id}", headers=headers)
        assert r2.get_json()["contract_value"] == "450000000.0000"
        assert r2.get_json()["currency"] == "NGN"

    def test_nonexistent_project_404s(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["projects:read"])
        r = client.get(f"/v1/projects/{uuid.uuid4()}", headers=headers)
        assert r.status_code == 404


class TestUpdateProject:
    def test_updates_status(self, app, db, client, seed_tenants, auth_headers):
        ids = _seed_company_client_pm(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["projects:manage"])

        r = client.post("/v1/projects", headers=headers, json={"company_id": ids["company_id"], "name": "P1"})
        project_id = r.get_json()["id"]

        r2 = client.put(f"/v1/projects/{project_id}", headers=headers, json={"status": "on_hold"})
        assert r2.status_code == 200
        assert r2.get_json()["status"] == "on_hold"

    def test_rejects_an_invalid_status_value(self, app, db, client, seed_tenants, auth_headers):
        ids = _seed_company_client_pm(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["projects:manage"])

        r = client.post("/v1/projects", headers=headers, json={"company_id": ids["company_id"], "name": "P1"})
        project_id = r.get_json()["id"]

        r2 = client.put(f"/v1/projects/{project_id}", headers=headers, json={"status": "not_a_real_status"})
        assert r2.status_code == 400


class TestProjectCrossTenantIsolation:
    def test_cannot_view_another_tenants_project(self, app, db, client, seed_tenants, auth_headers):
        ids = _seed_company_client_pm(db, seed_tenants["a"])
        headers_a = auth_headers("a", permissions=["projects:manage"])

        r = client.post("/v1/projects", headers=headers_a, json={"company_id": ids["company_id"], "name": "Tenant A Only"})
        project_id = r.get_json()["id"]

        headers_b = auth_headers("b", permissions=["projects:read"])
        r2 = client.get(f"/v1/projects/{project_id}", headers=headers_b)
        assert r2.status_code == 404

    def test_list_never_includes_another_tenants_projects(self, app, db, client, seed_tenants, auth_headers):
        ids = _seed_company_client_pm(db, seed_tenants["a"])
        headers_a = auth_headers("a", permissions=["projects:manage"])
        client.post("/v1/projects", headers=headers_a, json={"company_id": ids["company_id"], "name": "Tenant A Secret"})

        headers_b = auth_headers("b", permissions=["projects:read"])
        r = client.get("/v1/projects", headers=headers_b)
        names = [p["name"] for p in r.get_json()["data"]]
        assert "Tenant A Secret" not in names
