"""
Tests for app/platform_admin/ -- a real, separate cross-tenant admin
credential type, real tenant oversight, and real suspension
enforcement (checked at login, not cosmetic).
"""
from sqlalchemy import text


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def _create_platform_admin(db, email="admin@platform.test", password="adminpass123"):
    from app.platform_admin.services import create_platform_admin

    return create_platform_admin(email, password)


def _platform_admin_token(client, email="admin@platform.test", password="adminpass123"):
    r = client.post("/v1/platform-admin/auth/login", json={"email": email, "password": password})
    return r.get_json()["access_token"]


class TestPlatformAdminAuth:
    def test_login_with_correct_credentials_succeeds(self, app, db, client):
        _create_platform_admin(db)
        r = client.post("/v1/platform-admin/auth/login", json={"email": "admin@platform.test", "password": "adminpass123"})
        assert r.status_code == 200
        assert "access_token" in r.get_json()

    def test_login_with_wrong_password_fails(self, app, db, client):
        _create_platform_admin(db)
        r = client.post("/v1/platform-admin/auth/login", json={"email": "admin@platform.test", "password": "wrong"})
        assert r.status_code == 401

    def test_a_platform_admin_token_cannot_access_ordinary_tenant_routes(self, app, db, client):
        """The token carries no tenant_id and no permissions claim at
        all -- structurally incapable of passing require_permission,
        not just conventionally blocked."""
        _create_platform_admin(db)
        token = _platform_admin_token(client)
        r = client.get("/v1/bdc/clients", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403

    def test_an_ordinary_user_token_cannot_access_platform_admin_routes(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        r = client.get("/v1/platform-admin/tenants", headers=headers)
        assert r.status_code == 403


class TestPlatformAdminTenantOversight:
    def test_list_tenants_includes_real_cross_tenant_data(self, app, db, client, seed_tenants):
        _create_platform_admin(db)
        token = _platform_admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        r = client.get("/v1/platform-admin/tenants", headers=headers)
        assert r.status_code == 200
        tenant_ids = {t["id"] for t in r.get_json()["data"]}
        # Both tenant fixtures are visible -- genuine cross-tenant read,
        # not accidentally scoped to whichever tenant happened to be
        # "current" when this request started.
        assert str(seed_tenants["a"]) in tenant_ids
        assert str(seed_tenants["b"]) in tenant_ids

    def test_get_tenant_detail_for_a_real_tenant(self, app, db, client, seed_tenants):
        _create_platform_admin(db)
        token = _platform_admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        r = client.get(f"/v1/platform-admin/tenants/{seed_tenants['a']}", headers=headers)
        assert r.status_code == 200
        assert r.get_json()["id"] == str(seed_tenants["a"])

    def test_get_tenant_detail_for_a_nonexistent_tenant_404s(self, app, db, client):
        import uuid

        _create_platform_admin(db)
        token = _platform_admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        r = client.get(f"/v1/platform-admin/tenants/{uuid.uuid4()}", headers=headers)
        assert r.status_code == 404


class TestTenantSuspensionIsRealEnforcement:
    def test_suspending_a_tenant_actually_blocks_login(self, app, db, client):
        _create_platform_admin(db)
        admin_token = _platform_admin_token(client)
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        r = client.post("/v1/onboarding/signup", json={
            "company_name": "Suspension Test Co", "admin_email": "suspendtest@example.com", "admin_password": "testpassword123",
        })
        tenant_id = r.get_json()["tenant_id"]

        r_before = client.post("/v1/auth/login", json={"email": "suspendtest@example.com", "password": "testpassword123"})
        assert r_before.status_code == 200

        r_suspend = client.post(f"/v1/platform-admin/tenants/{tenant_id}/suspend", headers=admin_headers)
        assert r_suspend.status_code == 200
        assert r_suspend.get_json()["is_suspended"] is True

        r_after = client.post("/v1/auth/login", json={"email": "suspendtest@example.com", "password": "testpassword123"})
        assert r_after.status_code == 401

    def test_reactivating_restores_login(self, app, db, client):
        _create_platform_admin(db)
        admin_token = _platform_admin_token(client)
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        r = client.post("/v1/onboarding/signup", json={
            "company_name": "Reactivate Test Co", "admin_email": "reactivatetest@example.com", "admin_password": "testpassword123",
        })
        tenant_id = r.get_json()["tenant_id"]

        client.post(f"/v1/platform-admin/tenants/{tenant_id}/suspend", headers=admin_headers)
        r_reactivate = client.post(f"/v1/platform-admin/tenants/{tenant_id}/reactivate", headers=admin_headers)
        assert r_reactivate.status_code == 200
        assert r_reactivate.get_json()["is_suspended"] is False

        r_after = client.post("/v1/auth/login", json={"email": "reactivatetest@example.com", "password": "testpassword123"})
        assert r_after.status_code == 200
