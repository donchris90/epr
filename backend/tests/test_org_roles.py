"""
Tests for real role management (backend/app/org/) -- create, update,
delete, the permission catalog, and the real privilege-escalation
guard (a caller can never grant a role permissions they don't
themselves hold, unless they already have the "*" wildcard).
"""
from sqlalchemy import text


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


class TestPermissionsCatalog:
    def test_returns_a_real_grouped_catalog(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["org:read"])
        r = client.get("/v1/org/permissions-catalog", headers=headers)
        assert r.status_code == 200
        groups = r.get_json()["data"]
        assert len(groups) > 10
        for group in groups:
            assert group["permissions"]
            for perm in group["permissions"]:
                assert ":" in perm["code"]
                assert perm["label"]


class TestCreateRole:
    def test_admin_with_wildcard_can_grant_any_real_permission(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        r = client.post("/v1/org/roles", headers=headers, json={"name": "Site Engineer", "permission_set": ["exe:read", "exe:write", "hse:read"]})
        assert r.status_code == 201
        assert r.get_json()["permission_set"] == ["exe:read", "exe:write", "hse:read"]

    def test_rejects_an_unrecognized_permission(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        r = client.post("/v1/org/roles", headers=headers, json={"name": "Bad Role", "permission_set": ["totally:madeup"]})
        assert r.status_code == 400

    def test_rejects_a_duplicate_role_name(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        client.post("/v1/org/roles", headers=headers, json={"name": "Accountant", "permission_set": ["fin:read"]})
        r = client.post("/v1/org/roles", headers=headers, json={"name": "Accountant", "permission_set": ["fin:write"]})
        assert r.status_code == 409

    def test_requires_a_non_empty_name(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        r = client.post("/v1/org/roles", headers=headers, json={"name": "  ", "permission_set": ["fin:read"]})
        assert r.status_code == 400


class TestPrivilegeEscalationGuard:
    def test_a_limited_caller_cannot_grant_a_permission_they_lack(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["org:manage", "org:read", "bdc:read"])
        r = client.post("/v1/org/roles", headers=headers, json={"name": "Sneaky Role", "permission_set": ["billing:manage"]})
        assert r.status_code == 403

    def test_a_limited_caller_can_grant_exactly_what_they_hold(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["org:manage", "org:read", "bdc:read"])
        r = client.post("/v1/org/roles", headers=headers, json={"name": "Junior Coordinator", "permission_set": ["bdc:read"]})
        assert r.status_code == 201

    def test_guard_also_applies_to_updates_not_just_creation(self, app, db, client, seed_tenants, auth_headers):
        admin_headers = auth_headers("a", permissions=["*"])
        r = client.post("/v1/org/roles", headers=admin_headers, json={"name": "Editable Role", "permission_set": ["bdc:read"]})
        role_id = r.get_json()["id"]

        limited_headers = auth_headers("a", permissions=["org:manage", "org:read", "bdc:read"])
        r2 = client.put(f"/v1/org/roles/{role_id}", headers=limited_headers, json={"permission_set": ["workflow:admin"]})
        assert r2.status_code == 403

    def test_wildcard_holder_bypasses_the_guard_entirely(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        r = client.post("/v1/org/roles", headers=headers, json={"name": "Anything Role", "permission_set": ["workflow:admin", "billing:manage", "fin:manual_exception"]})
        assert r.status_code == 201


class TestUpdateRole:
    def test_updates_permission_set(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        r = client.post("/v1/org/roles", headers=headers, json={"name": "Growing Role", "permission_set": ["bdc:read"]})
        role_id = r.get_json()["id"]

        r2 = client.put(f"/v1/org/roles/{role_id}", headers=headers, json={"permission_set": ["bdc:read", "bdc:write"]})
        assert r2.status_code == 200
        assert r2.get_json()["permission_set"] == ["bdc:read", "bdc:write"]

    def test_nonexistent_role_404s(self, app, db, client, seed_tenants, auth_headers):
        import uuid

        headers = auth_headers("a", permissions=["*"])
        r = client.put(f"/v1/org/roles/{uuid.uuid4()}", headers=headers, json={"name": "Ghost"})
        assert r.status_code == 404


class TestDeleteRole:
    def test_deletes_an_unused_role(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        r = client.post("/v1/org/roles", headers=headers, json={"name": "Unused Role", "permission_set": ["bdc:read"]})
        role_id = r.get_json()["id"]

        r2 = client.delete(f"/v1/org/roles/{role_id}", headers=headers)
        assert r2.status_code == 204

    def test_refuses_to_delete_a_role_assigned_to_an_active_user(self, app, db, client, seed_tenants, auth_headers):
        from app.models.core import User
        from app.auth.jwt_utils import hash_password

        headers = auth_headers("a", permissions=["*"])
        r = client.post("/v1/org/roles", headers=headers, json={"name": "In Use Role", "permission_set": ["bdc:read"]})
        role_id = r.get_json()["id"]

        _as_tenant(db, seed_tenants["a"])
        db.session.add(User(tenant_id=seed_tenants["a"], email="roleuser@example.com", password_hash=hash_password("x"), role_id=role_id, status="active"))
        db.session.commit()

        r2 = client.delete(f"/v1/org/roles/{role_id}", headers=headers)
        assert r2.status_code == 409

    def test_refuses_to_delete_a_role_used_by_a_pending_invitation(self, app, db, client, seed_tenants, auth_headers):
        from unittest.mock import patch

        headers = auth_headers("a", permissions=["*", "org:manage", "org:read"])
        r = client.post("/v1/org/roles", headers=headers, json={"name": "Invited Role", "permission_set": ["bdc:read"]})
        role_id = r.get_json()["id"]

        with patch("app.org.services.send_email_notification"):
            r2 = client.post("/v1/org/invitations", headers=headers, json={"email": "pendingroleuser@example.com", "role_id": role_id})
        assert r2.status_code == 201

        r3 = client.delete(f"/v1/org/roles/{role_id}", headers=headers)
        assert r3.status_code == 409


class TestRoleCrossTenantIsolation:
    def test_cannot_see_another_tenants_roles(self, app, db, client, seed_tenants, auth_headers):
        headers_a = auth_headers("a", permissions=["*"])
        client.post("/v1/org/roles", headers=headers_a, json={"name": "Tenant A Only Role", "permission_set": ["bdc:read"]})

        headers_b = auth_headers("b", permissions=["org:read"])
        r = client.get("/v1/org/roles", headers=headers_b)
        names = [role["name"] for role in r.get_json()["data"]]
        assert "Tenant A Only Role" not in names
