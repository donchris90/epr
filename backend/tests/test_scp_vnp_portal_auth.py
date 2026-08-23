"""
Tests for real, previously genuinely missing functionality: Subcontractor
Portal (SCP) and Vendor Portal (VNP) self-service authentication.
Before this, neither SubcontractorPortalUser nor VendorPortalUser had
any password at all -- every real route required the internal staff
@require_permission grant, with no way for a subcontractor or vendor
to ever obtain a session token themselves. See
docs/SUBCONTRACTOR_VENDOR_PORTAL_GAPS.md for the full reasoning.
"""
import uuid

from sqlalchemy import text


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def _seed_scp_user(db, tenant_id, *, email="sub@example.com", password="a real password"):
    from app.modules.scp.models import SubcontractorPortalUser, SubcontractorPortalEmailIndex
    from app.auth.jwt_utils import hash_password

    _as_tenant(db, tenant_id)
    user = SubcontractorPortalUser(
        tenant_id=tenant_id, subcontractor_id=uuid.uuid4(), email=email,
        password_hash=hash_password(password), is_active=True,
    )
    db.session.add(user)
    db.session.flush()
    user_id = user.id
    db.session.add(SubcontractorPortalEmailIndex(email=email, portal_user_id=user_id, tenant_id=tenant_id))
    db.session.commit()
    return user_id


def _seed_vnp_user(db, tenant_id, *, email="vendor@example.com", password="a real password"):
    from app.modules.vnp.models import VendorPortalUser, VendorPortalEmailIndex
    from app.auth.jwt_utils import hash_password

    _as_tenant(db, tenant_id)
    user = VendorPortalUser(
        tenant_id=tenant_id, vendor_id=uuid.uuid4(), email=email,
        password_hash=hash_password(password), is_active=True,
    )
    db.session.add(user)
    db.session.flush()
    user_id = user.id
    db.session.add(VendorPortalEmailIndex(email=email, vendor_user_id=user_id, tenant_id=tenant_id))
    db.session.commit()
    return user_id


class TestSubcontractorPortalLogin:
    def test_real_login_with_correct_credentials(self, app, db, client, seed_tenants):
        _seed_scp_user(db, seed_tenants["a"])
        r = client.post("/v1/scp/auth/login", json={"email": "sub@example.com", "password": "a real password"})
        assert r.status_code == 200
        assert r.get_json()["access_token"]
        assert r.get_json()["refresh_token"]

    def test_wrong_password_rejected(self, app, db, client, seed_tenants):
        _seed_scp_user(db, seed_tenants["a"])
        r = client.post("/v1/scp/auth/login", json={"email": "sub@example.com", "password": "totally wrong"})
        assert r.status_code == 401

    def test_unknown_email_rejected(self, app, db, client):
        r = client.post("/v1/scp/auth/login", json={"email": "unknown@example.com", "password": "x"})
        assert r.status_code == 401

    def test_inactive_user_cannot_log_in(self, app, db, client, seed_tenants):
        from app.modules.scp.models import SubcontractorPortalUser

        user_id = _seed_scp_user(db, seed_tenants["a"])
        _as_tenant(db, seed_tenants["a"])
        SubcontractorPortalUser.query.filter_by(id=user_id).update({"is_active": False})
        db.session.commit()

        r = client.post("/v1/scp/auth/login", json={"email": "sub@example.com", "password": "a real password"})
        assert r.status_code == 401

    def test_real_token_works_on_a_protected_route(self, app, db, client, seed_tenants):
        user_id = _seed_scp_user(db, seed_tenants["a"])
        r_login = client.post("/v1/scp/auth/login", json={"email": "sub@example.com", "password": "a real password"})
        token = r_login.get_json()["access_token"]

        r_me = client.get("/v1/scp/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r_me.status_code == 200
        assert r_me.get_json()["id"] == str(user_id)

    def test_refresh_issues_a_real_new_access_token(self, app, db, client, seed_tenants):
        _seed_scp_user(db, seed_tenants["a"])
        r_login = client.post("/v1/scp/auth/login", json={"email": "sub@example.com", "password": "a real password"})
        refresh_token = r_login.get_json()["refresh_token"]

        r_refresh = client.post("/v1/scp/auth/refresh", headers={"Authorization": f"Bearer {refresh_token}"})
        assert r_refresh.status_code == 200
        assert r_refresh.get_json()["access_token"]

    def test_a_staff_refresh_token_cannot_mint_a_portal_access_token(self, app, db, client, seed_tenants, auth_headers):
        """Real regression coverage for the identical cross-portal
        confusion CLP's own refresh route already guards against."""
        from flask_jwt_extended import create_refresh_token

        with app.app_context():
            staff_refresh = create_refresh_token(
                identity="staff-1", additional_claims={"tenant_id": str(seed_tenants["a"]), "user_id": "staff-1", "permissions": ["*"]}
            )
        r = client.post("/v1/scp/auth/refresh", headers={"Authorization": f"Bearer {staff_refresh}"})
        assert r.status_code == 401

    def test_logout_revokes_the_real_refresh_token(self, app, db, client, seed_tenants):
        _seed_scp_user(db, seed_tenants["a"])
        r_login = client.post("/v1/scp/auth/login", json={"email": "sub@example.com", "password": "a real password"})
        refresh_token = r_login.get_json()["refresh_token"]

        r_logout = client.post("/v1/scp/auth/logout", headers={"Authorization": f"Bearer {refresh_token}"})
        assert r_logout.status_code == 200

        r_refresh_after = client.post("/v1/scp/auth/refresh", headers={"Authorization": f"Bearer {refresh_token}"})
        assert r_refresh_after.status_code == 401

    def test_a_portal_token_cannot_access_another_portal_users_account(self, app, db, client, seed_tenants):
        """Real regression coverage for the identical identity-spoofing
        fix CLP's own _get_client_user_or_404 already closes."""
        user_id = _seed_scp_user(db, seed_tenants["a"], email="sub1@example.com")
        _seed_scp_user(db, seed_tenants["a"], email="sub2@example.com")

        r_login = client.post("/v1/scp/auth/login", json={"email": "sub1@example.com", "password": "a real password"})
        token = r_login.get_json()["access_token"]

        other_user_id = None
        from app.modules.scp.models import SubcontractorPortalUser

        _as_tenant(db, seed_tenants["a"])
        other = SubcontractorPortalUser.query.filter_by(email="sub2@example.com").first()
        other_user_id = other.id

        r = client.get(f"/v1/scp/portal-users/{other_user_id}/claims?agreement_id={uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403


class TestSubcontractorChangePassword:
    def test_real_change_with_correct_current_password(self, app, db, client, seed_tenants):
        _seed_scp_user(db, seed_tenants["a"])
        r_login = client.post("/v1/scp/auth/login", json={"email": "sub@example.com", "password": "a real password"})
        token = r_login.get_json()["access_token"]

        r_change = client.post(
            "/v1/scp/auth/me/password", headers={"Authorization": f"Bearer {token}"},
            json={"current_password": "a real password", "new_password": "brand new password 456"},
        )
        assert r_change.status_code == 200

        r_login_new = client.post("/v1/scp/auth/login", json={"email": "sub@example.com", "password": "brand new password 456"})
        assert r_login_new.status_code == 200

    def test_wrong_current_password_is_rejected(self, app, db, client, seed_tenants):
        _seed_scp_user(db, seed_tenants["a"])
        r_login = client.post("/v1/scp/auth/login", json={"email": "sub@example.com", "password": "a real password"})
        token = r_login.get_json()["access_token"]

        r_change = client.post(
            "/v1/scp/auth/me/password", headers={"Authorization": f"Bearer {token}"},
            json={"current_password": "totally wrong", "new_password": "brand new password 456"},
        )
        assert r_change.status_code == 401


class TestVendorPortalLogin:
    def test_real_login_with_correct_credentials(self, app, db, client, seed_tenants):
        _seed_vnp_user(db, seed_tenants["a"])
        r = client.post("/v1/vnp/auth/login", json={"email": "vendor@example.com", "password": "a real password"})
        assert r.status_code == 200
        assert r.get_json()["access_token"]

    def test_wrong_password_rejected(self, app, db, client, seed_tenants):
        _seed_vnp_user(db, seed_tenants["a"])
        r = client.post("/v1/vnp/auth/login", json={"email": "vendor@example.com", "password": "wrong"})
        assert r.status_code == 401

    def test_real_token_works_on_a_protected_route(self, app, db, client, seed_tenants):
        user_id = _seed_vnp_user(db, seed_tenants["a"])
        r_login = client.post("/v1/vnp/auth/login", json={"email": "vendor@example.com", "password": "a real password"})
        token = r_login.get_json()["access_token"]

        r_me = client.get("/v1/vnp/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r_me.status_code == 200
        assert r_me.get_json()["id"] == str(user_id)


class TestVendorListPurchaseOrders:
    """Real coverage for the real, small gap closed while building
    this: PurchaseOrder.vendor_id already existed, but nothing let a
    vendor discover which of their own orders exist at all."""

    def test_lists_only_real_purchase_orders_belonging_to_this_vendor(self, app, db, client, seed_tenants):
        from app.modules.prc.models import PurchaseOrder, Vendor
        from app.modules.vnp.models import VendorPortalUser

        _as_tenant(db, seed_tenants["a"])
        vendor = Vendor(tenant_id=seed_tenants["a"], name="Real Vendor Co")
        other_vendor = Vendor(tenant_id=seed_tenants["a"], name="Other Vendor Co")
        db.session.add_all([vendor, other_vendor])
        db.session.flush()
        vendor_id = vendor.id
        other_vendor_id = other_vendor.id
        db.session.add(PurchaseOrder(tenant_id=seed_tenants["a"], vendor_id=vendor_id, po_number="PO-001", status="issued", total_value=100000))
        db.session.add(PurchaseOrder(tenant_id=seed_tenants["a"], vendor_id=other_vendor_id, po_number="PO-002", status="issued", total_value=200000))
        db.session.commit()

        from app.auth.jwt_utils import hash_password
        from app.modules.vnp.models import VendorPortalEmailIndex

        _as_tenant(db, seed_tenants["a"])
        user = VendorPortalUser(tenant_id=seed_tenants["a"], vendor_id=vendor_id, email="realvendor@example.com", password_hash=hash_password("x"), is_active=True)
        db.session.add(user)
        db.session.flush()
        user_id = user.id
        db.session.add(VendorPortalEmailIndex(email="realvendor@example.com", vendor_user_id=user_id, tenant_id=seed_tenants["a"]))
        db.session.commit()

        r_login = client.post("/v1/vnp/auth/login", json={"email": "realvendor@example.com", "password": "x"})
        token = r_login.get_json()["access_token"]

        r = client.get(f"/v1/vnp/vendor-users/{user_id}/purchase-orders", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        pos = r.get_json()["data"]
        assert len(pos) == 1
        assert pos[0]["po_number"] == "PO-001"

    def test_a_portal_token_cannot_access_another_vendors_account(self, app, db, client, seed_tenants):
        user_id = _seed_vnp_user(db, seed_tenants["a"], email="vendor1@example.com")
        other_id = _seed_vnp_user(db, seed_tenants["a"], email="vendor2@example.com")

        r_login = client.post("/v1/vnp/auth/login", json={"email": "vendor1@example.com", "password": "a real password"})
        token = r_login.get_json()["access_token"]

        r = client.get(f"/v1/vnp/vendor-users/{other_id}/purchase-orders", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403
