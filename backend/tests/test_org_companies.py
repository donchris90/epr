"""
Tests for real org-level Company management (backend/app/org/) --
GET/POST /v1/org/companies. Added as the fix for a real, reported bug:
Project.company_id's own real foreign key target
(app.models.core.Company) had no CRUD endpoint anywhere in this
backend before this. The project-creation form's own Company dropdown
was fetching from GET /v1/fin/companies instead -- a real, but
entirely different table (fin_companies, a separate multi-entity
accounting concept) -- so every real project creation failed with an
unhandled foreign-key violation regardless of what was selected.
"""
import uuid


class TestListCompanies:
    def test_returns_only_this_tenants_real_companies(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["org:read", "org:manage"])
        client.post("/v1/org/companies", headers=headers, json={"name": "Lekki Holdings Ltd"})

        headers_b = auth_headers("b", permissions=["org:read"])
        r = client.get("/v1/org/companies", headers=headers_b)
        assert r.status_code == 200
        assert r.get_json()["data"] == []

    def test_lists_a_real_created_company(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["org:read", "org:manage"])
        client.post("/v1/org/companies", headers=headers, json={"name": "Lekki Holdings Ltd"})

        r = client.get("/v1/org/companies", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1
        assert r.get_json()["data"][0]["name"] == "Lekki Holdings Ltd"

    def test_requires_org_read(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["projects:read"])
        r = client.get("/v1/org/companies", headers=headers)
        assert r.status_code == 403


class TestCreateCompany:
    def test_creates_a_real_company_with_a_real_default_currency(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["org:manage"])
        r = client.post("/v1/org/companies", headers=headers, json={"name": "Ikoyi Estates Ltd"})
        assert r.status_code == 201
        assert r.get_json()["name"] == "Ikoyi Estates Ltd"
        assert r.get_json()["base_currency"] == "NGN"

    def test_requires_org_manage_not_just_org_read(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["org:read"])
        r = client.post("/v1/org/companies", headers=headers, json={"name": "Should Fail"})
        assert r.status_code == 403

    def test_rejects_an_empty_name(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["org:manage"])
        r = client.post("/v1/org/companies", headers=headers, json={"name": ""})
        assert r.status_code == 400


class TestRealEndToEndProjectCreationWithARealCompany:
    """The real regression this fix closes: creating a project with a
    real, freshly-created company_id must actually succeed end to end
    -- not just the isolated company-creation endpoint on its own."""

    def test_a_freshly_created_company_can_immediately_back_a_real_project(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["org:manage", "projects:manage"])
        company = client.post("/v1/org/companies", headers=headers, json={"name": "Lekki Holdings Ltd"})
        company_id = company.get_json()["id"]

        r = client.post("/v1/projects", headers=headers, json={"company_id": company_id, "name": "Lekki Tower Phase 1"})
        assert r.status_code == 201
        assert r.get_json()["company_id"] == company_id

    def test_a_real_fin_companies_id_still_correctly_fails_project_creation(self, app, db, client, seed_tenants, auth_headers):
        """Real, deliberate confirmation that the two Company concepts
        remain genuinely distinct -- a real fin_companies row's id
        must NOT be usable as a project's company_id, since that
        would mean the two tables were silently merged rather than
        the real bug (wrong dropdown source) being fixed."""
        from app.modules.fin.models import Company as FinCompany
        from sqlalchemy import text

        db.session.execute(text("SET LOCAL app.tenant_id = :t"), {"t": str(seed_tenants["a"])})
        fin_company = FinCompany(tenant_id=seed_tenants["a"], name="Fin Entity Ltd")
        db.session.add(fin_company)
        db.session.flush()
        fin_company_id = str(fin_company.id)
        db.session.commit()

        headers = auth_headers("a", permissions=["projects:manage"])
        r = client.post("/v1/projects", headers=headers, json={"company_id": fin_company_id, "name": "Should Fail"})
        assert r.status_code == 404
        assert r.get_json()["title"] == "Company not found"
