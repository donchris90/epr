"""
Tests for the client-facing portal build (Module 22 / CLP):

  - Real client login (POST /v1/clp/auth/login), a genuinely new
    endpoint -- ClientPortalUser had no password of any kind before
    this build. See app/modules/clp/services.py:authenticate_client_user.
  - The two security fixes made alongside the frontend build:
      1. A client token may only ever act as its own client_user_id
         (app/modules/clp/routes.py:_get_client_user_or_404).
      2. Approving a certificate/variation order verifies the
         record's OWN project matches the project_id the client
         claimed, not just that the client is assigned to that
         project_id (app/modules/clp/services.py:
         approve_variation_order_as_client / approve_certificate_as_client).
  - The new client-scoped read endpoints (projects, documents,
    certificates, variation orders, invoices).

Follows the existing test_projects_crud.py fixture pattern
(_as_tenant / _seed_company_client_pm) rather than inventing a new one.
"""
import uuid
from datetime import date

import pytest
from flask_jwt_extended import create_access_token, create_refresh_token
from sqlalchemy import text


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def _seed_project(db, tenant_id, *, name="Lekki Tower"):
    from app.models.core import Company, Project

    _as_tenant(db, tenant_id)
    company = Company(tenant_id=tenant_id, name="Test Co")
    db.session.add(company)
    db.session.flush()
    project = Project(tenant_id=tenant_id, company_id=company.id, name=name, status="active", start_date=date(2026, 1, 1))
    db.session.add(project)
    db.session.flush()
    project_id = project.id  # captured before commit -- see this file's own note on why
    db.session.commit()
    return project_id


def _seed_contract(db, tenant_id, *, project_id, contract_value=1_000_000):
    from app.modules.ctm.models import Contract

    _as_tenant(db, tenant_id)
    contract = Contract(
        tenant_id=tenant_id,
        tender_id=uuid.uuid4(),
        project_id=project_id,
        contract_number=f"C-{uuid.uuid4().hex[:8]}",
        contract_value=contract_value,
        currency="NGN",
    )
    db.session.add(contract)
    db.session.flush()
    contract_id = contract.id  # captured before commit -- see this file's own note on why
    db.session.commit()
    return contract_id


def _seed_client_user(db, tenant_id, *, email="client@example.com", password="a real password", active=True):
    """
    Real bug found and fixed here, not just in application code: the
    original version of this helper (and _seed_project/_seed_contract
    above, same pattern) accessed .id AFTER db.session.commit() -- a
    real commit, not a savepoint, which ends the transaction that
    _as_tenant's SET LOCAL was scoped to. Under this session's default
    expire_on_commit=True, that access triggers a fresh refresh query
    for the primary key, and with the transaction (and its tenant
    context) already gone, RLS's own policy expression fails trying
    to cast an empty app.tenant_id to uuid -- reproduced directly via
    a real pytest run with diagnostics before concluding this was the
    cause, not assumed. Fixed the same way this codebase's own
    application code fixes it elsewhere: flush (which populates the
    PK without ending the transaction) and capture the id as a plain
    value before commit.
    """
    from app.modules.clp.models import ClientPortalUser, ClientPortalEmailIndex
    from app.auth.jwt_utils import hash_password

    _as_tenant(db, tenant_id)
    user = ClientPortalUser(
        tenant_id=tenant_id,
        client_organization_name="Acme Developments",
        email=email,
        password_hash=hash_password(password) if password else None,
        is_active=active,
    )
    db.session.add(user)
    db.session.flush()
    user_id = user.id  # captured before commit -- see this function's own docstring
    db.session.add(ClientPortalEmailIndex(tenant_id=tenant_id, email=email, client_user_id=user_id))
    db.session.commit()
    return user_id


def _assign(db, tenant_id, *, client_user_id, project_id):
    from app.modules.clp.models import ClientProjectAssignment

    _as_tenant(db, tenant_id)
    db.session.add(ClientProjectAssignment(tenant_id=tenant_id, client_user_id=client_user_id, project_id=project_id))
    db.session.commit()


def _client_headers(app, *, tenant_id, client_user_id, permissions=None):
    with app.app_context():
        token = create_access_token(
            identity=str(client_user_id),
            additional_claims={
                "tenant_id": str(tenant_id),
                "user_id": str(client_user_id),
                "permissions": permissions if permissions is not None else ["clp:read", "clp:write"],
                "is_client": True,
            },
        )
    return {"Authorization": f"Bearer {token}"}


class TestClientLogin:
    def test_logs_in_with_correct_credentials(self, app, db, client, seed_tenants):
        _seed_client_user(db, seed_tenants["a"], email="client@example.com", password="correct horse battery staple")

        r = client.post("/v1/clp/auth/login", json={"email": "client@example.com", "password": "correct horse battery staple"})

        assert r.status_code == 200
        assert "access_token" in r.get_json()
        assert "refresh_token" in r.get_json()

    def test_rejects_wrong_password(self, app, db, client, seed_tenants):
        _seed_client_user(db, seed_tenants["a"], email="client@example.com", password="correct horse battery staple")

        r = client.post("/v1/clp/auth/login", json={"email": "client@example.com", "password": "wrong password"})

        assert r.status_code == 401

    def test_rejects_unknown_email(self, app, db, client, seed_tenants):
        r = client.post("/v1/clp/auth/login", json={"email": "nobody@example.com", "password": "whatever"})
        assert r.status_code == 401

    def test_rejects_inactive_client_user(self, app, db, client, seed_tenants):
        _seed_client_user(db, seed_tenants["a"], email="client@example.com", password="correct horse battery staple", active=False)

        r = client.post("/v1/clp/auth/login", json={"email": "client@example.com", "password": "correct horse battery staple"})

        assert r.status_code == 401

    def test_same_email_can_belong_to_two_different_tenants(self, app, db, client, seed_tenants):
        """The real reason clp_email_index isn't a copy of
        email_tenant_index: a client organization can legitimately be
        a client of two different contractors (tenants) with the same
        contact email, each with their own password."""
        _seed_client_user(db, seed_tenants["a"], email="shared@example.com", password="tenant a password")
        _seed_client_user(db, seed_tenants["b"], email="shared@example.com", password="tenant b password")

        r_a = client.post("/v1/clp/auth/login", json={"email": "shared@example.com", "password": "tenant a password"})
        r_b = client.post("/v1/clp/auth/login", json={"email": "shared@example.com", "password": "tenant b password"})

        assert r_a.status_code == 200
        assert r_b.status_code == 200
        assert r_a.get_json()["access_token"] != r_b.get_json()["access_token"]


class TestClientIdentityGuard:
    """The impersonation-prevention fix: a client token may only ever
    act as its own client_user_id, regardless of what its clp:read/
    clp:write permission grant would otherwise allow."""

    def test_client_cannot_list_another_clients_projects(self, app, db, client, seed_tenants):
        project_id = _seed_project(db, seed_tenants["a"])
        me = _seed_client_user(db, seed_tenants["a"], email="me@example.com")
        someone_else = _seed_client_user(db, seed_tenants["a"], email="other@example.com")
        _assign(db, seed_tenants["a"], client_user_id=someone_else, project_id=project_id)

        headers = _client_headers(app, tenant_id=seed_tenants["a"], client_user_id=me)
        r = client.get(f"/v1/clp/client-users/{someone_else}/projects", headers=headers)

        assert r.status_code == 403

    def test_staff_admin_token_can_still_act_on_behalf_of_any_client(self, app, db, client, seed_tenants, auth_headers):
        """The admin page's whole reason for existing -- must keep
        working exactly as before for a staff (non is_client) token."""
        project_id = _seed_project(db, seed_tenants["a"])
        client_user_id = _seed_client_user(db, seed_tenants["a"])
        _assign(db, seed_tenants["a"], client_user_id=client_user_id, project_id=project_id)

        staff_headers = auth_headers("a", permissions=["clp:read"])
        r = client.get(f"/v1/clp/client-users/{client_user_id}/projects", headers=staff_headers)

        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1


class TestProjectOwnershipOnDecisions:
    """The second fix: assert_client_project_access alone only checks
    the client is assigned to the CLAIMED project_id -- it says
    nothing about which project the target VO/certificate actually
    belongs to. These tests would have passed incorrectly before that
    fix (a client deciding on a record from a project they aren't
    even looking at, as long as they were assigned to *some* other
    project and could guess the record's id)."""

    def test_cannot_decide_a_variation_order_belonging_to_a_different_project(self, app, db, client, seed_tenants, auth_headers):
        from app.modules.bil.models import VariationOrder

        project_a = _seed_project(db, seed_tenants["a"], name="Project A")
        project_b = _seed_project(db, seed_tenants["a"], name="Project B")
        contract_b = _seed_contract(db, seed_tenants["a"], project_id=project_b)

        _as_tenant(db, seed_tenants["a"])
        vo = VariationOrder(tenant_id=seed_tenants["a"], contract_id=contract_b, description="Extra piling", status="pending")
        db.session.add(vo)
        db.session.flush()
        vo_id = vo.id  # captured before commit -- see _seed_client_user's own docstring on why
        db.session.commit()

        client_user_id = _seed_client_user(db, seed_tenants["a"])
        # Assigned to BOTH projects -- so assert_client_project_access
        # alone would pass for project_a; only the ownership check
        # catches that this VO is actually project_b's.
        _assign(db, seed_tenants["a"], client_user_id=client_user_id, project_id=project_a)
        _assign(db, seed_tenants["a"], client_user_id=client_user_id, project_id=project_b)

        headers = _client_headers(app, tenant_id=seed_tenants["a"], client_user_id=client_user_id)
        r = client.post(
            f"/v1/clp/client-users/{client_user_id}/variation-orders/{vo_id}/decide",
            headers=headers,
            json={"project_id": str(project_a), "decision": "approved"},
        )

        assert r.status_code == 403

        _as_tenant(db, seed_tenants["a"])
        db.session.refresh(vo)
        assert vo.status == "pending"

    def test_can_decide_a_variation_order_belonging_to_the_claimed_project(self, app, db, client, seed_tenants):
        from app.modules.bil.models import VariationOrder

        project_id = _seed_project(db, seed_tenants["a"])
        contract_id = _seed_contract(db, seed_tenants["a"], project_id=project_id)

        _as_tenant(db, seed_tenants["a"])
        vo = VariationOrder(tenant_id=seed_tenants["a"], contract_id=contract_id, description="Extra piling", status="pending")
        db.session.add(vo)
        db.session.flush()
        vo_id = vo.id  # captured before commit -- see _seed_client_user's own docstring on why
        db.session.commit()

        client_user_id = _seed_client_user(db, seed_tenants["a"])
        _assign(db, seed_tenants["a"], client_user_id=client_user_id, project_id=project_id)

        headers = _client_headers(app, tenant_id=seed_tenants["a"], client_user_id=client_user_id)
        r = client.post(
            f"/v1/clp/client-users/{client_user_id}/variation-orders/{vo_id}/decide",
            headers=headers,
            json={"project_id": str(project_id), "decision": "approved"},
        )

        assert r.status_code == 201
        assert r.get_json()["decision"] == "approved"

    def test_cannot_approve_a_certificate_with_no_project_id_set(self, app, db, client, seed_tenants):
        """Fail-closed: a certificate created without project_id (an
        optional field on the internal staff schema) must never be
        approvable by a client, even one assigned to the project it
        was informally meant for -- there's no real way to confirm
        that without the field being set."""
        from app.modules.bil.models import ProgressCertificate

        project_id = _seed_project(db, seed_tenants["a"])

        _as_tenant(db, seed_tenants["a"])
        certificate = ProgressCertificate(
            tenant_id=seed_tenants["a"], certificate_number="PC-001", status="submitted", project_id=None
        )
        db.session.add(certificate)
        db.session.flush()
        certificate_id = certificate.id  # captured before commit -- see _seed_client_user's own docstring on why
        db.session.commit()

        client_user_id = _seed_client_user(db, seed_tenants["a"])
        _assign(db, seed_tenants["a"], client_user_id=client_user_id, project_id=project_id)

        headers = _client_headers(app, tenant_id=seed_tenants["a"], client_user_id=client_user_id)
        r = client.post(
            f"/v1/clp/client-users/{client_user_id}/certificates/{certificate_id}/decide",
            headers=headers,
            json={"project_id": str(project_id), "decision": "approved"},
        )

        assert r.status_code == 403


class TestClientScopedReads:
    def test_lists_only_assigned_projects(self, app, db, client, seed_tenants):
        assigned = _seed_project(db, seed_tenants["a"], name="Assigned Project")
        _seed_project(db, seed_tenants["a"], name="Not Assigned Project")

        client_user_id = _seed_client_user(db, seed_tenants["a"])
        _assign(db, seed_tenants["a"], client_user_id=client_user_id, project_id=assigned)

        headers = _client_headers(app, tenant_id=seed_tenants["a"], client_user_id=client_user_id)
        r = client.get(f"/v1/clp/client-users/{client_user_id}/projects", headers=headers)

        assert r.status_code == 200
        names = [p["name"] for p in r.get_json()["data"]]
        assert names == ["Assigned Project"]

    def test_project_detail_403s_for_an_unassigned_project(self, app, db, client, seed_tenants):
        other_project = _seed_project(db, seed_tenants["a"])
        client_user_id = _seed_client_user(db, seed_tenants["a"])

        headers = _client_headers(app, tenant_id=seed_tenants["a"], client_user_id=client_user_id)
        r = client.get(f"/v1/clp/client-users/{client_user_id}/projects/{other_project}", headers=headers)

        assert r.status_code == 403

    def test_certificates_are_filtered_to_the_project_and_exclude_drafts(self, app, db, client, seed_tenants):
        from app.modules.bil.models import ProgressCertificate

        project_id = _seed_project(db, seed_tenants["a"])
        other_project_id = _seed_project(db, seed_tenants["a"])

        _as_tenant(db, seed_tenants["a"])
        db.session.add_all(
            [
                ProgressCertificate(tenant_id=seed_tenants["a"], certificate_number="PC-001", status="submitted", project_id=project_id),
                ProgressCertificate(tenant_id=seed_tenants["a"], certificate_number="PC-002", status="draft", project_id=project_id),
                ProgressCertificate(tenant_id=seed_tenants["a"], certificate_number="PC-003", status="submitted", project_id=other_project_id),
            ]
        )
        db.session.commit()

        client_user_id = _seed_client_user(db, seed_tenants["a"])
        _assign(db, seed_tenants["a"], client_user_id=client_user_id, project_id=project_id)

        headers = _client_headers(app, tenant_id=seed_tenants["a"], client_user_id=client_user_id)
        r = client.get(f"/v1/clp/client-users/{client_user_id}/projects/{project_id}/certificates", headers=headers)

        assert r.status_code == 200
        numbers = [c["certificate_number"] for c in r.get_json()["data"]]
        assert numbers == ["PC-001"]

    def test_variation_orders_are_resolved_through_the_contract(self, app, db, client, seed_tenants):
        from app.modules.bil.models import VariationOrder

        project_id = _seed_project(db, seed_tenants["a"])
        contract_id = _seed_contract(db, seed_tenants["a"], project_id=project_id)

        _as_tenant(db, seed_tenants["a"])
        db.session.add(VariationOrder(tenant_id=seed_tenants["a"], contract_id=contract_id, description="Extra piling", status="pending"))
        db.session.commit()

        client_user_id = _seed_client_user(db, seed_tenants["a"])
        _assign(db, seed_tenants["a"], client_user_id=client_user_id, project_id=project_id)

        headers = _client_headers(app, tenant_id=seed_tenants["a"], client_user_id=client_user_id)
        r = client.get(f"/v1/clp/client-users/{client_user_id}/projects/{project_id}/variation-orders", headers=headers)

        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1
        assert r.get_json()["data"][0]["description"] == "Extra piling"


class TestRefreshTokenFamiliesAreSeparate:
    """A client refresh token must never work at the staff /v1/auth/refresh
    endpoint, and vice versa -- see app/auth/routes.py's own docstring."""

    def test_client_refresh_token_rejected_by_staff_refresh_endpoint(self, app, db, client, seed_tenants):
        client_user_id = _seed_client_user(db, seed_tenants["a"])
        with app.app_context():
            refresh_token = create_refresh_token(
                identity=str(client_user_id),
                additional_claims={
                    "tenant_id": str(seed_tenants["a"]),
                    "user_id": str(client_user_id),
                    "permissions": ["clp:read", "clp:write"],
                    "is_client": True,
                },
            )

        r = client.post("/v1/auth/refresh", headers={"Authorization": f"Bearer {refresh_token}"})
        assert r.status_code == 401

    def test_staff_refresh_token_rejected_by_client_refresh_endpoint(self, app, db, client, seed_tenants):
        with app.app_context():
            refresh_token = create_refresh_token(
                identity=str(uuid.uuid4()),
                additional_claims={
                    "tenant_id": str(seed_tenants["a"]),
                    "user_id": str(uuid.uuid4()),
                    "role_id": None,
                    "permissions": ["*"],
                },
            )

        r = client.post("/v1/clp/auth/refresh", headers={"Authorization": f"Bearer {refresh_token}"})
        assert r.status_code == 401


class TestChangePassword:
    def test_requires_correct_current_password(self, app, db, client, seed_tenants):
        client_user_id = _seed_client_user(db, seed_tenants["a"], password="original password")
        headers = _client_headers(app, tenant_id=seed_tenants["a"], client_user_id=client_user_id)

        r = client.post(
            "/v1/clp/auth/me/password",
            headers=headers,
            json={"current_password": "wrong", "new_password": "brand new password"},
        )

        assert r.status_code == 401

    def test_changes_password_and_new_password_works_at_login(self, app, db, client, seed_tenants):
        client_user_id = _seed_client_user(db, seed_tenants["a"], email="client@example.com", password="original password")
        headers = _client_headers(app, tenant_id=seed_tenants["a"], client_user_id=client_user_id)

        r = client.post(
            "/v1/clp/auth/me/password",
            headers=headers,
            json={"current_password": "original password", "new_password": "brand new password"},
        )
        assert r.status_code == 200

        r = client.post("/v1/clp/auth/login", json={"email": "client@example.com", "password": "brand new password"})
        assert r.status_code == 200
