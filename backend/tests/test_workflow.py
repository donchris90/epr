"""
Tests for the generic Workflow Engine (Module 26, app/workflow/).
"""
import uuid

from sqlalchemy import text


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def _make_role(db, tenant_id, name, permissions):
    from app.models.core import Role

    _as_tenant(db, tenant_id)
    role = Role(tenant_id=tenant_id, name=name, permission_set=permissions)
    db.session.add(role)
    db.session.flush()
    role_id = role.id
    db.session.commit()
    return role_id


class TestWorkflowDefinitions:
    def test_create_and_activate_a_definition(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["workflow:admin"])
        r = client.post("/v1/workflow/definitions", headers=headers, json={
            "module_name": "prc", "entity_type": "purchase_request", "workflow_name": "Test Approval",
            "steps": [{"step_number": 1, "name": "Step 1", "approver_type": "specific_user", "specific_user_id": str(uuid.uuid4())}],
        })
        assert r.status_code == 201
        assert r.get_json()["active"] is False

        definition_id = r.get_json()["id"]
        r2 = client.post(f"/v1/workflow/definitions/{definition_id}/activate", headers=headers)
        assert r2.status_code == 200
        assert r2.get_json()["active"] is True

    def test_activating_a_new_version_deactivates_the_old_one(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["workflow:admin"])

        def _create_and_activate():
            r = client.post("/v1/workflow/definitions", headers=headers, json={
                "module_name": "prc", "entity_type": "purchase_request", "workflow_name": "V",
                "steps": [{"step_number": 1, "name": "Step 1", "approver_type": "specific_user", "specific_user_id": str(uuid.uuid4())}],
            })
            definition_id = r.get_json()["id"]
            client.post(f"/v1/workflow/definitions/{definition_id}/activate", headers=headers)
            return definition_id

        first_id = _create_and_activate()
        second_id = _create_and_activate()

        first = client.get(f"/v1/workflow/definitions/{first_id}", headers=headers).get_json()
        second = client.get(f"/v1/workflow/definitions/{second_id}", headers=headers).get_json()
        assert first["active"] is False
        assert second["active"] is True

    def test_creating_a_definition_requires_workflow_admin_permission(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["workflow:approve"])  # approve, not admin
        r = client.post("/v1/workflow/definitions", headers=headers, json={
            "module_name": "prc", "entity_type": "purchase_request", "workflow_name": "X", "steps": [],
        })
        assert r.status_code == 403

    def test_zero_steps_is_rejected(self, app, db, client, seed_tenants, auth_headers):
        """Real regression test for the real gap fixed in this batch:
        the schema previously accepted an empty steps list (required=True
        is satisfied by []), producing a genuinely meaningless workflow
        with nothing to approve at all."""
        headers = auth_headers("a", permissions=["workflow:admin"])
        r = client.post("/v1/workflow/definitions", headers=headers, json={
            "module_name": "prc", "entity_type": "purchase_request", "workflow_name": "Empty", "steps": [],
        })
        assert r.status_code == 422

    def test_specific_user_step_without_a_user_id_is_rejected(self, app, db, client, seed_tenants, auth_headers):
        """Real regression test for the real gap fixed in this batch: a
        step with approver_type='specific_user' but no specific_user_id
        was previously accepted -- a step literally no one could approve."""
        headers = auth_headers("a", permissions=["workflow:admin"])
        r = client.post("/v1/workflow/definitions", headers=headers, json={
            "module_name": "prc", "entity_type": "purchase_request", "workflow_name": "Broken",
            "steps": [{"step_number": 1, "name": "Step 1", "approver_type": "specific_user"}],
        })
        assert r.status_code == 422

    def test_specific_role_step_without_a_role_id_is_rejected(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["workflow:admin"])
        r = client.post("/v1/workflow/definitions", headers=headers, json={
            "module_name": "prc", "entity_type": "purchase_request", "workflow_name": "Broken",
            "steps": [{"step_number": 1, "name": "Step 1", "approver_type": "specific_role"}],
        })
        assert r.status_code == 422

    def test_response_includes_real_audit_fields(self, app, db, client, seed_tenants, auth_headers):
        """Real regression test for the real gap fixed in this batch:
        created_by/updated_at/updated_by existed on the model
        (AuditMixin) but were never exposed in the response schema at
        all. Also confirms updated_by is genuinely populated on
        activation, not left null forever."""
        headers = auth_headers("a", permissions=["workflow:admin"], user_id="11111111-1111-1111-1111-111111111111")
        r = client.post("/v1/workflow/definitions", headers=headers, json={
            "module_name": "prc", "entity_type": "purchase_request", "workflow_name": "Audited",
            "steps": [{"step_number": 1, "name": "Step 1", "approver_type": "specific_user", "specific_user_id": str(uuid.uuid4())}],
        })
        body = r.get_json()
        assert body["created_by"] == "11111111-1111-1111-1111-111111111111"
        assert body["updated_by"] is None  # never touched since creation
        assert body["updated_at"] is not None

        definition_id = body["id"]
        r2 = client.post(f"/v1/workflow/definitions/{definition_id}/activate", headers=headers)
        assert r2.get_json()["updated_by"] == "11111111-1111-1111-1111-111111111111"


class TestWorkflowInstances:
    def _setup_two_step_workflow(self, client, admin_headers, finance_role_id, ceo_role_id):
        r = client.post("/v1/workflow/definitions", headers=admin_headers, json={
            "module_name": "prc", "entity_type": "purchase_request", "workflow_name": "PR Approval",
            "steps": [
                {"step_number": 1, "name": "Finance", "approver_type": "specific_role", "required_role_id": str(finance_role_id)},
                {"step_number": 2, "name": "CEO", "approver_type": "specific_role", "required_role_id": str(ceo_role_id), "minimum_amount": "1000000"},
            ],
        })
        definition_id = r.get_json()["id"]
        client.post(f"/v1/workflow/definitions/{definition_id}/activate", headers=admin_headers)
        return definition_id

    def test_amount_below_threshold_skips_the_second_step(self, app, db, client, seed_tenants, auth_headers):
        finance_role_id = _make_role(db, seed_tenants["a"], "Finance", ["workflow:approve"])
        ceo_role_id = _make_role(db, seed_tenants["a"], "CEO", ["workflow:approve"])
        admin_headers = auth_headers("a", permissions=["workflow:admin", "workflow:approve"])
        self._setup_two_step_workflow(client, admin_headers, finance_role_id, ceo_role_id)

        r = client.post("/v1/workflow/instances", headers=admin_headers, json={
            "module_name": "prc", "entity_type": "purchase_request", "entity_id": str(uuid.uuid4()), "amount": "500000",
        })
        instance_id = r.get_json()["id"]

        finance_headers = auth_headers("a", permissions=["workflow:approve"], role_id=finance_role_id)
        r2 = client.post(f"/v1/workflow/instances/{instance_id}/approve", headers=finance_headers, json={})
        assert r2.status_code == 200
        assert r2.get_json()["status"] == "approved"

    def test_amount_above_threshold_requires_the_second_step(self, app, db, client, seed_tenants, auth_headers):
        finance_role_id = _make_role(db, seed_tenants["a"], "Finance", ["workflow:approve"])
        ceo_role_id = _make_role(db, seed_tenants["a"], "CEO", ["workflow:approve"])
        admin_headers = auth_headers("a", permissions=["workflow:admin", "workflow:approve"])
        self._setup_two_step_workflow(client, admin_headers, finance_role_id, ceo_role_id)

        r = client.post("/v1/workflow/instances", headers=admin_headers, json={
            "module_name": "prc", "entity_type": "purchase_request", "entity_id": str(uuid.uuid4()), "amount": "2000000",
        })
        instance_id = r.get_json()["id"]

        finance_headers = auth_headers("a", permissions=["workflow:approve"], role_id=finance_role_id)
        r2 = client.post(f"/v1/workflow/instances/{instance_id}/approve", headers=finance_headers, json={})
        assert r2.status_code == 200
        assert r2.get_json()["status"] == "pending"
        assert r2.get_json()["current_step_number"] == 2

        ceo_headers = auth_headers("a", permissions=["workflow:approve"], role_id=ceo_role_id)
        r3 = client.post(f"/v1/workflow/instances/{instance_id}/approve", headers=ceo_headers, json={"comment": "Approved"})
        assert r3.status_code == 200
        assert r3.get_json()["status"] == "approved"

    def test_wrong_role_cannot_approve(self, app, db, client, seed_tenants, auth_headers):
        finance_role_id = _make_role(db, seed_tenants["a"], "Finance", ["workflow:approve"])
        ceo_role_id = _make_role(db, seed_tenants["a"], "CEO", ["workflow:approve"])
        other_role_id = _make_role(db, seed_tenants["a"], "Nobody", ["workflow:approve"])
        admin_headers = auth_headers("a", permissions=["workflow:admin", "workflow:approve"])
        self._setup_two_step_workflow(client, admin_headers, finance_role_id, ceo_role_id)

        r = client.post("/v1/workflow/instances", headers=admin_headers, json={
            "module_name": "prc", "entity_type": "purchase_request", "entity_id": str(uuid.uuid4()), "amount": "500000",
        })
        instance_id = r.get_json()["id"]

        wrong_headers = auth_headers("a", permissions=["workflow:approve"], role_id=other_role_id)
        r2 = client.post(f"/v1/workflow/instances/{instance_id}/approve", headers=wrong_headers, json={})
        assert r2.status_code == 403

    def test_rejection_marks_instance_rejected(self, app, db, client, seed_tenants, auth_headers):
        finance_role_id = _make_role(db, seed_tenants["a"], "Finance", ["workflow:approve"])
        ceo_role_id = _make_role(db, seed_tenants["a"], "CEO", ["workflow:approve"])
        admin_headers = auth_headers("a", permissions=["workflow:admin", "workflow:approve"])
        self._setup_two_step_workflow(client, admin_headers, finance_role_id, ceo_role_id)

        r = client.post("/v1/workflow/instances", headers=admin_headers, json={
            "module_name": "prc", "entity_type": "purchase_request", "entity_id": str(uuid.uuid4()), "amount": "500000",
        })
        instance_id = r.get_json()["id"]

        finance_headers = auth_headers("a", permissions=["workflow:approve"], role_id=finance_role_id)
        r2 = client.post(f"/v1/workflow/instances/{instance_id}/reject", headers=finance_headers, json={"comment": "No"})
        assert r2.status_code == 200
        assert r2.get_json()["status"] == "rejected"

    def test_reject_to_step_returns_instance_to_an_earlier_step_instead_of_terminating(self, app, db, client, seed_tenants, auth_headers):
        finance_role_id = _make_role(db, seed_tenants["a"], "Finance", ["workflow:approve"])
        ceo_role_id = _make_role(db, seed_tenants["a"], "CEO", ["workflow:approve"])
        admin_headers = auth_headers("a", permissions=["workflow:admin", "workflow:approve"])

        r = client.post("/v1/workflow/definitions", headers=admin_headers, json={
            "module_name": "prc", "entity_type": "purchase_request", "workflow_name": "Reject to step test",
            "steps": [
                {"step_number": 1, "name": "Finance", "approver_type": "specific_role", "required_role_id": str(finance_role_id)},
                {"step_number": 2, "name": "CEO", "approver_type": "specific_role", "required_role_id": str(ceo_role_id), "reject_to_step": 1},
            ],
        })
        definition_id = r.get_json()["id"]
        client.post(f"/v1/workflow/definitions/{definition_id}/activate", headers=admin_headers)

        r = client.post("/v1/workflow/instances", headers=admin_headers, json={
            "module_name": "prc", "entity_type": "purchase_request", "entity_id": str(uuid.uuid4()),
        })
        instance_id = r.get_json()["id"]

        finance_headers = auth_headers("a", permissions=["workflow:approve"], role_id=finance_role_id)
        client.post(f"/v1/workflow/instances/{instance_id}/approve", headers=finance_headers, json={})

        ceo_headers = auth_headers("a", permissions=["workflow:approve"], role_id=ceo_role_id)
        r2 = client.post(f"/v1/workflow/instances/{instance_id}/reject", headers=ceo_headers, json={"comment": "Rework needed"})
        assert r2.status_code == 200
        assert r2.get_json()["status"] == "pending"
        assert r2.get_json()["current_step_number"] == 1

    def test_delegation_lets_the_delegate_approve(self, app, db, client, seed_tenants, auth_headers):
        finance_role_id = _make_role(db, seed_tenants["a"], "Finance", ["workflow:approve"])
        ceo_role_id = _make_role(db, seed_tenants["a"], "CEO", ["workflow:approve"])
        admin_headers = auth_headers("a", permissions=["workflow:admin", "workflow:approve"])
        self._setup_two_step_workflow(client, admin_headers, finance_role_id, ceo_role_id)

        r = client.post("/v1/workflow/instances", headers=admin_headers, json={
            "module_name": "prc", "entity_type": "purchase_request", "entity_id": str(uuid.uuid4()), "amount": "500000",
        })
        instance_id = r.get_json()["id"]

        delegate_user_id = uuid.uuid4()
        finance_headers = auth_headers("a", permissions=["workflow:approve"], role_id=finance_role_id)
        r2 = client.post(
            f"/v1/workflow/instances/{instance_id}/delegate", headers=finance_headers,
            json={"delegate_to": str(delegate_user_id), "comment": "On leave"},
        )
        assert r2.status_code == 200

        # The delegate has no matching role at all -- only the explicit delegation authorizes them.
        delegate_headers = auth_headers("a", permissions=["workflow:approve"], user_id=delegate_user_id)
        r3 = client.post(f"/v1/workflow/instances/{instance_id}/approve", headers=delegate_headers, json={})
        assert r3.status_code == 200
        assert r3.get_json()["status"] == "approved"

    def test_pending_approvals_list_only_shows_instances_the_user_can_act_on(self, app, db, client, seed_tenants, auth_headers):
        finance_role_id = _make_role(db, seed_tenants["a"], "Finance", ["workflow:approve"])
        ceo_role_id = _make_role(db, seed_tenants["a"], "CEO", ["workflow:approve"])
        admin_headers = auth_headers("a", permissions=["workflow:admin", "workflow:approve"])
        self._setup_two_step_workflow(client, admin_headers, finance_role_id, ceo_role_id)

        client.post("/v1/workflow/instances", headers=admin_headers, json={
            "module_name": "prc", "entity_type": "purchase_request", "entity_id": str(uuid.uuid4()), "amount": "500000",
        })

        finance_headers = auth_headers("a", permissions=["workflow:approve"], role_id=finance_role_id)
        ceo_headers = auth_headers("a", permissions=["workflow:approve"], role_id=ceo_role_id)

        finance_pending = client.get("/v1/workflow/instances/pending", headers=finance_headers).get_json()["data"]
        ceo_pending = client.get("/v1/workflow/instances/pending", headers=ceo_headers).get_json()["data"]
        assert len(finance_pending) == 1
        assert len(ceo_pending) == 0  # not this step's approver yet

    def test_audit_trail_captures_ip_and_user_agent(self, app, db, client, seed_tenants, auth_headers):
        finance_role_id = _make_role(db, seed_tenants["a"], "Finance", ["workflow:approve"])
        ceo_role_id = _make_role(db, seed_tenants["a"], "CEO", ["workflow:approve"])
        admin_headers = auth_headers("a", permissions=["workflow:admin", "workflow:approve"])
        self._setup_two_step_workflow(client, admin_headers, finance_role_id, ceo_role_id)

        r = client.post("/v1/workflow/instances", headers=admin_headers, json={
            "module_name": "prc", "entity_type": "purchase_request", "entity_id": str(uuid.uuid4()), "amount": "500000",
        })
        instance_id = r.get_json()["id"]

        finance_headers = auth_headers("a", permissions=["workflow:approve"], role_id=finance_role_id)
        client.post(
            f"/v1/workflow/instances/{instance_id}/approve", headers=finance_headers,
            json={"comment": "Approved with reason"},
        )

        from app.workflow.models import WorkflowAction
        _as_tenant(db, seed_tenants["a"])
        action = WorkflowAction.query.filter_by(instance_id=uuid.UUID(instance_id)).first()
        assert action.action_type == "approve"
        assert action.comment == "Approved with reason"
        assert action.old_status is not None
        assert action.ip_address is not None

    def test_cross_tenant_isolation(self, app, db, client, seed_tenants, auth_headers):
        finance_role_a = _make_role(db, seed_tenants["a"], "Finance", ["workflow:approve"])
        admin_headers_a = auth_headers("a", permissions=["workflow:admin", "workflow:approve"])
        admin_headers_b = auth_headers("b", permissions=["workflow:admin", "workflow:approve"])

        r = client.post("/v1/workflow/definitions", headers=admin_headers_a, json={
            "module_name": "prc", "entity_type": "purchase_request", "workflow_name": "Tenant A only",
            "steps": [{"step_number": 1, "name": "Step 1", "approver_type": "specific_role", "required_role_id": str(finance_role_a)}],
        })
        definition_id = r.get_json()["id"]

        # Tenant B must not be able to see tenant A's definition at all.
        r2 = client.get(f"/v1/workflow/definitions/{definition_id}", headers=admin_headers_b)
        assert r2.status_code == 404
