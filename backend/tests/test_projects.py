"""
Tests for GET /v1/projects (app/projects/routes.py).

Regression coverage for a real, previously-missing gap found in a
broader audit: Project is referenced by nearly every module in this
codebase, but no route anywhere let a client list or search projects
-- every frontend screen and the mobile app were reduced to a raw
"paste a project UUID" text field because there was genuinely nothing
to select from.
"""
import uuid

from sqlalchemy import text


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def _seed_projects(db, tenant_id):
    from app.models.core import Company, Project

    _as_tenant(db, tenant_id)
    company = Company(tenant_id=tenant_id, name="Test Co")
    db.session.add(company)
    db.session.flush()

    projects = [
        Project(tenant_id=tenant_id, company_id=company.id, name="Lekki Tower Phase 1", status="active"),
        Project(tenant_id=tenant_id, company_id=company.id, name="Lekki Tower Phase 2", status="active"),
        Project(tenant_id=tenant_id, company_id=company.id, name="Abuja Mall Renovation", status="completed"),
    ]
    db.session.add_all(projects)
    db.session.commit()


class TestListProjects:
    def test_lists_all_projects_for_the_tenant(self, app, db, client, seed_tenants, auth_headers):
        _seed_projects(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["projects:read"])

        r = client.get("/v1/projects", headers=headers)
        assert r.status_code == 200
        names = {p["name"] for p in r.get_json()["data"]}
        assert names == {"Lekki Tower Phase 1", "Lekki Tower Phase 2", "Abuja Mall Renovation"}

    def test_search_filters_by_name_case_insensitively(self, app, db, client, seed_tenants, auth_headers):
        _seed_projects(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["projects:read"])

        r = client.get("/v1/projects?search=LEKKI", headers=headers)
        assert r.status_code == 200
        names = {p["name"] for p in r.get_json()["data"]}
        assert names == {"Lekki Tower Phase 1", "Lekki Tower Phase 2"}

    def test_status_filters_exactly(self, app, db, client, seed_tenants, auth_headers):
        _seed_projects(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["projects:read"])

        r = client.get("/v1/projects?status=completed", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1
        assert r.get_json()["data"][0]["name"] == "Abuja Mall Renovation"

    def test_results_are_sorted_by_name(self, app, db, client, seed_tenants, auth_headers):
        _seed_projects(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["projects:read"])

        r = client.get("/v1/projects", headers=headers)
        names = [p["name"] for p in r.get_json()["data"]]
        assert names == sorted(names)

    def test_cross_tenant_isolation(self, app, db, client, seed_tenants, auth_headers):
        _seed_projects(db, seed_tenants["a"])
        headers_b = auth_headers("b", permissions=["projects:read"])

        r = client.get("/v1/projects", headers=headers_b)
        assert r.status_code == 200
        assert r.get_json()["data"] == []

    def test_requires_the_real_permission(self, app, db, client, seed_tenants, auth_headers):
        _seed_projects(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["hse:read"])  # some other, unrelated permission

        r = client.get("/v1/projects", headers=headers)
        assert r.status_code == 403

    def test_no_token_is_rejected(self, app, db, client):
        r = client.get("/v1/projects")
        assert r.status_code in (401, 403)  # matches this app's existing, established no-auth behavior
