"""
Tests for HSE's Permit to Work workflow integration
(app/modules/hse/services.py:issue_permit_to_work/finalize_permit_approval).

Regression coverage for a real, previously-unprotected safety-control
gap found while wiring this up: every permit -- including hot work,
confined space entry, and working at height -- self-approved
immediately on creation, with approved_by never even recorded (the
route didn't pass an actor at all). Any single user holding hse:write
could self-issue an "approved" permit for hazardous work with zero
accountability for who approved it.
"""
import uuid

from sqlalchemy import text


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def _make_role(db, tenant_id):
    from app.models.core import Role

    _as_tenant(db, tenant_id)
    role = Role(tenant_id=tenant_id, name="HSE Officer", permission_set=["hse:write", "workflow:approve", "workflow:admin"])
    db.session.add(role)
    db.session.flush()
    role_id = role.id
    db.session.commit()
    return role_id


def _activate_workflow(client, headers, role_id):
    r = client.post("/v1/workflow/definitions", headers=headers, json={
        "module_name": "hse", "entity_type": "permit_to_work", "workflow_name": "Permit Approval",
        "steps": [{"step_number": 1, "name": "HSE Officer", "approver_type": "specific_role", "required_role_id": str(role_id)}],
    })
    definition_id = r.get_json()["id"]
    client.post(f"/v1/workflow/definitions/{definition_id}/activate", headers=headers)


class TestPermitWithoutWorkflow:
    """Backward compatibility, plus the accountability fix: a tenant
    without a configured workflow still gets immediate approval, but
    now approved_by is actually recorded (it never was before)."""

    def test_permit_self_approves_with_real_approved_by_now_tracked(self, app, db, client, seed_tenants, auth_headers):
        user_id = uuid.uuid4()
        headers = auth_headers("a", permissions=["hse:write"], user_id=user_id)

        r = client.post("/v1/hse/permits", headers=headers, json={
            "project_id": str(uuid.uuid4()), "permit_type": "hot_work", "description": "Welding",
        })
        assert r.status_code == 201
        assert r.get_json()["status"] == "approved"
        assert r.get_json()["approved_by"] == str(user_id)
        assert r.get_json()["approved_at"] is not None


class TestPermitWithWorkflow:
    def test_permit_created_draft_and_cannot_activate_until_approved(self, app, db, client, seed_tenants, auth_headers):
        role_id = _make_role(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["hse:write", "hse:approve", "workflow:admin", "workflow:approve"], role_id=role_id)
        _activate_workflow(client, headers, role_id)

        r = client.post("/v1/hse/permits", headers=headers, json={
            "project_id": str(uuid.uuid4()), "permit_type": "confined_space", "description": "Tank inspection",
        })
        assert r.status_code == 201
        assert r.get_json()["status"] == "draft"
        assert r.get_json()["approved_by"] is None
        permit_id = r.get_json()["id"]

        r2 = client.post(f"/v1/hse/permits/{permit_id}/activate", headers=headers, json={})
        assert r2.status_code == 409

    def test_finalize_blocked_while_workflow_still_pending(self, app, db, client, seed_tenants, auth_headers):
        role_id = _make_role(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["hse:write", "hse:approve", "workflow:admin", "workflow:approve"], role_id=role_id)
        _activate_workflow(client, headers, role_id)

        r = client.post("/v1/hse/permits", headers=headers, json={
            "project_id": str(uuid.uuid4()), "permit_type": "working_at_height", "description": "Roof work",
        })
        permit_id = r.get_json()["id"]

        r2 = client.post(f"/v1/hse/permits/{permit_id}/finalize-approval", headers=headers, json={})
        assert r2.status_code == 409

    def test_full_approval_flow_then_activation_succeeds(self, app, db, client, seed_tenants, auth_headers):
        role_id = _make_role(db, seed_tenants["a"])
        user_id = uuid.uuid4()
        headers = auth_headers("a", permissions=["hse:write", "hse:approve", "workflow:admin", "workflow:approve"], role_id=role_id, user_id=user_id)
        _activate_workflow(client, headers, role_id)

        r = client.post("/v1/hse/permits", headers=headers, json={
            "project_id": str(uuid.uuid4()), "permit_type": "excavation", "description": "Trenching",
        })
        permit_id = r.get_json()["id"]

        instances = client.get("/v1/workflow/instances?module_name=hse&entity_type=permit_to_work", headers=headers).get_json()["data"]
        instance_id = [i for i in instances if i["entity_id"] == permit_id][0]["id"]
        client.post(f"/v1/workflow/instances/{instance_id}/approve", headers=headers, json={})

        r2 = client.post(f"/v1/hse/permits/{permit_id}/finalize-approval", headers=headers, json={})
        assert r2.status_code == 200
        assert r2.get_json()["status"] == "approved"
        assert r2.get_json()["approved_by"] == str(user_id)

        r3 = client.post(f"/v1/hse/permits/{permit_id}/activate", headers=headers, json={})
        assert r3.status_code == 200
        assert r3.get_json()["status"] == "active"

    def test_cannot_finalize_an_already_approved_permit(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["hse:write"])  # no workflow configured for this tenant

        r = client.post("/v1/hse/permits", headers=headers, json={
            "project_id": str(uuid.uuid4()), "permit_type": "hot_work", "description": "No workflow",
        })
        permit_id = r.get_json()["id"]  # self-approved immediately

        r2 = client.post(f"/v1/hse/permits/{permit_id}/finalize-approval", headers=headers, json={})
        assert r2.status_code == 409
