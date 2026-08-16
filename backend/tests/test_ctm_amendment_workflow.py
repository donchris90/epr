"""
Tests for CTM's Contract Amendment workflow integration
(app/modules/ctm/services.py:record_amendment/finalize_amendment).

Regression coverage for a real, previously-unprotected control gap
found while wiring this up: every amendment self-approved immediately
on creation (approved_by was always the same actor who created it) --
any single user holding ctm:approve could change a contract's value or
completion date alone, despite fields that suggested a real
second-approval control existed.
"""
import uuid

from sqlalchemy import text


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def _seed_contract(db, tenant_id, *, contract_value=1000000):
    from app.modules.ctm.models import Contract

    _as_tenant(db, tenant_id)
    contract = Contract(tenant_id=tenant_id, tender_id=uuid.uuid4(), contract_number=f"C-{uuid.uuid4()}", contract_value=contract_value)
    db.session.add(contract)
    db.session.flush()
    contract_id = contract.id
    db.session.commit()
    return contract_id


class TestAmendmentWithoutWorkflow:
    """Backward compatibility: a tenant that hasn't configured a
    workflow for ("ctm", "contract_amendment") must see identical
    behavior to before this integration existed."""

    def test_price_amendment_self_approves_and_applies_immediately(self, app, db, client, seed_tenants, auth_headers):
        contract_id = _seed_contract(db, seed_tenants["a"], contract_value=1000000)
        headers = auth_headers("a", permissions=["ctm:approve", "ctm:read"])

        r = client.post(f"/v1/ctm/contracts/{contract_id}/amendments", headers=headers, json={
            "amendment_type": "price", "description": "Extra scope", "price_delta": "50000",
        })
        assert r.status_code == 201
        assert r.get_json()["status"] == "approved"
        assert r.get_json()["approved_at"] is not None

        r2 = client.get(f"/v1/ctm/contracts/{contract_id}", headers=headers)
        assert r2.get_json()["contract_value"] == "1050000.0000"


class TestAmendmentWithWorkflow:
    def _activate_workflow(self, client, headers, role_id):
        r = client.post("/v1/workflow/definitions", headers=headers, json={
            "module_name": "ctm", "entity_type": "contract_amendment", "workflow_name": "Amendment Approval",
            "steps": [{"step_number": 1, "name": "Approver", "approver_type": "specific_role", "required_role_id": str(role_id)}],
        })
        definition_id = r.get_json()["id"]
        client.post(f"/v1/workflow/definitions/{definition_id}/activate", headers=headers)

    def _make_role(self, db, tenant_id):
        from app.models.core import Role

        _as_tenant(db, tenant_id)
        role = Role(tenant_id=tenant_id, name="Approver", permission_set=["ctm:approve", "workflow:approve", "workflow:admin"])
        db.session.add(role)
        db.session.flush()
        role_id = role.id
        db.session.commit()
        return role_id

    def test_amendment_is_pending_and_contract_value_unchanged_until_approved(self, app, db, client, seed_tenants, auth_headers):
        role_id = self._make_role(db, seed_tenants["a"])
        contract_id = _seed_contract(db, seed_tenants["a"], contract_value=1000000)
        headers = auth_headers("a", permissions=["ctm:approve", "ctm:read", "workflow:admin", "workflow:approve"], role_id=role_id)
        self._activate_workflow(client, headers, role_id)

        r = client.post(f"/v1/ctm/contracts/{contract_id}/amendments", headers=headers, json={
            "amendment_type": "price", "description": "Scope change", "price_delta": "100000",
        })
        assert r.status_code == 201
        assert r.get_json()["status"] == "pending"
        assert r.get_json()["approved_at"] is None

        r2 = client.get(f"/v1/ctm/contracts/{contract_id}", headers=headers)
        assert r2.get_json()["contract_value"] == "1000000.0000"  # unchanged

    def test_finalize_blocked_while_workflow_still_pending(self, app, db, client, seed_tenants, auth_headers):
        role_id = self._make_role(db, seed_tenants["a"])
        contract_id = _seed_contract(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["ctm:approve", "ctm:read", "workflow:admin", "workflow:approve"], role_id=role_id)
        self._activate_workflow(client, headers, role_id)

        r = client.post(f"/v1/ctm/contracts/{contract_id}/amendments", headers=headers, json={
            "amendment_type": "price", "description": "Scope change", "price_delta": "100000",
        })
        amendment_id = r.get_json()["id"]

        r2 = client.post(f"/v1/ctm/contracts/{contract_id}/amendments/{amendment_id}/finalize", headers=headers, json={})
        assert r2.status_code == 409

    def test_finalize_applies_the_mutation_once_workflow_approves(self, app, db, client, seed_tenants, auth_headers):
        role_id = self._make_role(db, seed_tenants["a"])
        contract_id = _seed_contract(db, seed_tenants["a"], contract_value=1000000)
        headers = auth_headers("a", permissions=["ctm:approve", "ctm:read", "workflow:admin", "workflow:approve"], role_id=role_id)
        self._activate_workflow(client, headers, role_id)

        r = client.post(f"/v1/ctm/contracts/{contract_id}/amendments", headers=headers, json={
            "amendment_type": "price", "description": "Scope change", "price_delta": "100000",
        })
        amendment_id = r.get_json()["id"]

        instances = client.get("/v1/workflow/instances?module_name=ctm&entity_type=contract_amendment", headers=headers).get_json()["data"]
        instance_id = [i for i in instances if i["entity_id"] == amendment_id][0]["id"]
        client.post(f"/v1/workflow/instances/{instance_id}/approve", headers=headers, json={})

        r2 = client.post(f"/v1/ctm/contracts/{contract_id}/amendments/{amendment_id}/finalize", headers=headers, json={})
        assert r2.status_code == 200
        assert r2.get_json()["status"] == "approved"

        r3 = client.get(f"/v1/ctm/contracts/{contract_id}", headers=headers)
        assert r3.get_json()["contract_value"] == "1100000.0000"

    def test_time_amendment_extends_completion_date_only_after_approval(self, app, db, client, seed_tenants, auth_headers):
        from app.modules.ctm.models import Contract

        role_id = self._make_role(db, seed_tenants["a"])
        _as_tenant(db, seed_tenants["a"])
        contract = Contract(
            tenant_id=seed_tenants["a"], tender_id=uuid.uuid4(), contract_number=f"C-{uuid.uuid4()}",
            contract_value=1000000, completion_date="2027-01-01",
        )
        db.session.add(contract)
        db.session.flush()
        contract_id = contract.id
        db.session.commit()

        headers = auth_headers("a", permissions=["ctm:approve", "ctm:read", "workflow:admin", "workflow:approve"], role_id=role_id)
        self._activate_workflow(client, headers, role_id)

        r = client.post(f"/v1/ctm/contracts/{contract_id}/amendments", headers=headers, json={
            "amendment_type": "time", "description": "Weather delay", "time_extension_days": 14,
        })
        amendment_id = r.get_json()["id"]

        r_before = client.get(f"/v1/ctm/contracts/{contract_id}", headers=headers)
        assert r_before.get_json()["completion_date"] == "2027-01-01"  # unchanged while pending

        instances = client.get("/v1/workflow/instances?module_name=ctm&entity_type=contract_amendment", headers=headers).get_json()["data"]
        instance_id = [i for i in instances if i["entity_id"] == amendment_id][0]["id"]
        client.post(f"/v1/workflow/instances/{instance_id}/approve", headers=headers, json={})
        client.post(f"/v1/ctm/contracts/{contract_id}/amendments/{amendment_id}/finalize", headers=headers, json={})

        r_after = client.get(f"/v1/ctm/contracts/{contract_id}", headers=headers)
        assert r_after.get_json()["completion_date"] == "2027-01-15"

    def test_cannot_finalize_an_already_approved_amendment(self, app, db, client, seed_tenants, auth_headers):
        contract_id = _seed_contract(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["ctm:approve", "ctm:read"])

        r = client.post(f"/v1/ctm/contracts/{contract_id}/amendments", headers=headers, json={
            "amendment_type": "price", "description": "No workflow configured", "price_delta": "10000",
        })
        amendment_id = r.get_json()["id"]  # self-approved immediately, no workflow active

        r2 = client.post(f"/v1/ctm/contracts/{contract_id}/amendments/{amendment_id}/finalize", headers=headers, json={})
        assert r2.status_code == 409
