"""
Workflow step due dates, escalation, and the overdue-escalation task.
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def _make_role(db, tenant_id, name):
    from app.models.core import Role

    _as_tenant(db, tenant_id)
    role = Role(tenant_id=tenant_id, name=name, permission_set=["workflow:approve"])
    db.session.add(role)
    db.session.flush()
    role_id = role.id
    db.session.commit()
    return role_id


def _make_user(db, tenant_id, role_id):
    from app.models.core import User

    _as_tenant(db, tenant_id)
    user = User(tenant_id=tenant_id, email=f"{uuid.uuid4().hex[:8]}@example.com", password_hash="x", role_id=role_id)
    db.session.add(user)
    db.session.flush()
    uid = user.id
    db.session.commit()
    return uid


def _define(client, headers, steps, name="Escalation test"):
    r = client.post("/v1/workflow/definitions", headers=headers, json={
        "module_name": "prc", "entity_type": "purchase_request", "workflow_name": name, "steps": steps,
    })
    assert r.status_code == 201, r.get_json()
    client.post(f"/v1/workflow/definitions/{r.get_json()['id']}/activate", headers=headers)
    return r.get_json()


def _start(client, headers, amount=None):
    body = {"module_name": "prc", "entity_type": "purchase_request", "entity_id": str(uuid.uuid4())}
    if amount:
        body["amount"] = amount
    r = client.post("/v1/workflow/instances", headers=headers, json=body)
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def _set_due(db, tenant_id, instance_id, due):
    from app.workflow.models import WorkflowInstance

    _as_tenant(db, tenant_id)
    inst = db.session.get(WorkflowInstance, uuid.UUID(instance_id))
    inst.step_due_at = due
    db.session.commit()


def _parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


class TestStepDueDate:
    def test_due_date_is_set_from_the_first_steps_timeout(self, app, db, client, seed_tenants, auth_headers):
        role = _make_role(db, seed_tenants["a"], "Finance")
        admin = auth_headers("a", permissions=["workflow:admin", "workflow:approve"])
        _define(client, admin, [{"step_number": 1, "name": "F", "approver_type": "specific_role",
                                 "required_role_id": str(role), "timeout_hours": 24}])
        inst = _start(client, admin)
        due = _parse(inst["step_due_at"])
        expected = datetime.now(timezone.utc) + timedelta(hours=24)
        assert abs((due - expected).total_seconds()) < 60
        assert inst["escalated_at"] is None

    def test_no_timeout_means_no_due_date(self, app, db, client, seed_tenants, auth_headers):
        role = _make_role(db, seed_tenants["a"], "Finance")
        admin = auth_headers("a", permissions=["workflow:admin", "workflow:approve"])
        _define(client, admin, [{"step_number": 1, "name": "F", "approver_type": "specific_role", "required_role_id": str(role)}])
        assert _start(client, admin)["step_due_at"] is None

    def test_advancing_recomputes_the_due_date_and_finishing_clears_it(self, app, db, client, seed_tenants, auth_headers):
        r1, r2 = _make_role(db, seed_tenants["a"], "One"), _make_role(db, seed_tenants["a"], "Two")
        admin = auth_headers("a", permissions=["workflow:admin", "workflow:approve"])
        _define(client, admin, [
            {"step_number": 1, "name": "One", "approver_type": "specific_role", "required_role_id": str(r1), "timeout_hours": 2},
            {"step_number": 2, "name": "Two", "approver_type": "specific_role", "required_role_id": str(r2), "timeout_hours": 48},
        ])
        inst = _start(client, admin)
        first_due = _parse(inst["step_due_at"])

        step1 = client.post(f"/v1/workflow/instances/{inst['id']}/approve",
                            headers=auth_headers("a", permissions=["workflow:approve"], role_id=r1), json={}).get_json()
        assert step1["current_step_number"] == 2
        assert _parse(step1["step_due_at"]) - first_due > timedelta(hours=40)  # now the 48h step

        done = client.post(f"/v1/workflow/instances/{inst['id']}/approve",
                           headers=auth_headers("a", permissions=["workflow:approve"], role_id=r2), json={}).get_json()
        assert done["status"] == "approved"
        assert done["step_due_at"] is None

    def test_a_parallel_group_is_due_at_its_strictest_timeout(self, app, db, client, seed_tenants, auth_headers):
        r1, r2 = _make_role(db, seed_tenants["a"], "P1"), _make_role(db, seed_tenants["a"], "P2")
        admin = auth_headers("a", permissions=["workflow:admin", "workflow:approve"])
        _define(client, admin, [
            {"step_number": 1, "name": "A", "approver_type": "specific_role", "required_role_id": str(r1), "timeout_hours": 72},
            {"step_number": 1, "name": "B", "approver_type": "specific_role", "required_role_id": str(r2), "timeout_hours": 6, "parallel": True},
        ])
        due = _parse(_start(client, admin)["step_due_at"])
        assert abs((due - (datetime.now(timezone.utc) + timedelta(hours=6))).total_seconds()) < 60


class TestManualEscalation:
    def test_cannot_escalate_a_step_with_no_target(self, app, db, client, seed_tenants, auth_headers):
        role = _make_role(db, seed_tenants["a"], "Approver")
        admin = auth_headers("a", permissions=["workflow:admin", "workflow:approve"])
        _define(client, admin, [{"step_number": 1, "name": "S", "approver_type": "specific_role", "required_role_id": str(role)}])
        inst = _start(client, admin)
        r = client.post(f"/v1/workflow/instances/{inst['id']}/escalate", headers=admin, json={})
        assert r.status_code == 400
        assert "no escalation target" in r.get_json()["title"].lower()

    def test_target_cannot_act_before_escalation_but_can_after(self, app, db, client, seed_tenants, auth_headers):
        role = _make_role(db, seed_tenants["a"], "Approver")
        target = uuid.uuid4()
        admin = auth_headers("a", permissions=["workflow:admin", "workflow:approve"])
        _define(client, admin, [{"step_number": 1, "name": "S", "approver_type": "specific_role",
                                 "required_role_id": str(role), "escalate_to_user_id": str(target)}])
        inst = _start(client, admin)
        target_headers = auth_headers("a", permissions=["workflow:approve"], user_id=target)

        assert client.post(f"/v1/workflow/instances/{inst['id']}/approve", headers=target_headers, json={}).status_code == 403

        esc = client.post(f"/v1/workflow/instances/{inst['id']}/escalate", headers=admin, json={"comment": "Urgent"})
        assert esc.status_code == 200
        body = esc.get_json()
        assert body["escalated_at"] is not None
        last = body["actions"][-1]
        assert last["action_type"] == "escalate" and last["comment"] == "Urgent"

        done = client.post(f"/v1/workflow/instances/{inst['id']}/approve", headers=target_headers, json={})
        assert done.status_code == 200 and done.get_json()["status"] == "approved"

    def test_role_based_target_works(self, app, db, client, seed_tenants, auth_headers):
        role, exec_role = _make_role(db, seed_tenants["a"], "Approver"), _make_role(db, seed_tenants["a"], "Exec")
        admin = auth_headers("a", permissions=["workflow:admin", "workflow:approve"])
        _define(client, admin, [{"step_number": 1, "name": "S", "approver_type": "specific_role",
                                 "required_role_id": str(role), "escalate_to_role_id": str(exec_role)}])
        inst = _start(client, admin)
        exec_headers = auth_headers("a", permissions=["workflow:approve"], role_id=exec_role)
        assert client.post(f"/v1/workflow/instances/{inst['id']}/approve", headers=exec_headers, json={}).status_code == 403
        client.post(f"/v1/workflow/instances/{inst['id']}/escalate", headers=admin, json={})
        assert client.post(f"/v1/workflow/instances/{inst['id']}/approve", headers=exec_headers, json={}).status_code == 200

    def test_escalating_twice_is_rejected(self, app, db, client, seed_tenants, auth_headers):
        role = _make_role(db, seed_tenants["a"], "Approver")
        admin = auth_headers("a", permissions=["workflow:admin", "workflow:approve"])
        _define(client, admin, [{"step_number": 1, "name": "S", "approver_type": "specific_role",
                                 "required_role_id": str(role), "escalate_to_user_id": str(uuid.uuid4())}])
        inst = _start(client, admin)
        assert client.post(f"/v1/workflow/instances/{inst['id']}/escalate", headers=admin, json={}).status_code == 200
        again = client.post(f"/v1/workflow/instances/{inst['id']}/escalate", headers=admin, json={})
        assert again.status_code == 400 and "already been escalated" in again.get_json()["title"]

    def test_unrelated_user_cannot_escalate(self, app, db, client, seed_tenants, auth_headers):
        role, other = _make_role(db, seed_tenants["a"], "Approver"), _make_role(db, seed_tenants["a"], "Other")
        admin = auth_headers("a", permissions=["workflow:admin", "workflow:approve"])
        _define(client, admin, [{"step_number": 1, "name": "S", "approver_type": "specific_role",
                                 "required_role_id": str(role), "escalate_to_user_id": str(uuid.uuid4())}])
        inst = _start(client, admin)
        stranger = auth_headers("a", permissions=["workflow:approve"], role_id=other)
        assert client.post(f"/v1/workflow/instances/{inst['id']}/escalate", headers=stranger, json={}).status_code == 403

    def test_current_approver_can_escalate(self, app, db, client, seed_tenants, auth_headers):
        role = _make_role(db, seed_tenants["a"], "Approver")
        admin = auth_headers("a", permissions=["workflow:admin", "workflow:approve"])
        _define(client, admin, [{"step_number": 1, "name": "S", "approver_type": "specific_role",
                                 "required_role_id": str(role), "escalate_to_user_id": str(uuid.uuid4())}])
        inst = _start(client, admin)
        approver = auth_headers("a", permissions=["workflow:approve"], role_id=role)
        assert client.post(f"/v1/workflow/instances/{inst['id']}/escalate", headers=approver, json={}).status_code == 200

    def test_advancing_clears_the_escalation_for_the_next_step(self, app, db, client, seed_tenants, auth_headers):
        r1, r2 = _make_role(db, seed_tenants["a"], "One"), _make_role(db, seed_tenants["a"], "Two")
        target = uuid.uuid4()
        admin = auth_headers("a", permissions=["workflow:admin", "workflow:approve"])
        _define(client, admin, [
            {"step_number": 1, "name": "One", "approver_type": "specific_role", "required_role_id": str(r1), "escalate_to_user_id": str(target)},
            {"step_number": 2, "name": "Two", "approver_type": "specific_role", "required_role_id": str(r2)},
        ])
        inst = _start(client, admin)
        client.post(f"/v1/workflow/instances/{inst['id']}/escalate", headers=admin, json={})
        moved = client.post(f"/v1/workflow/instances/{inst['id']}/approve",
                            headers=auth_headers("a", permissions=["workflow:approve"], user_id=target), json={}).get_json()
        assert moved["current_step_number"] == 2 and moved["escalated_at"] is None
        # The step-1 escalation target gets no special rights on step 2.
        assert client.post(f"/v1/workflow/instances/{inst['id']}/approve",
                           headers=auth_headers("a", permissions=["workflow:approve"], user_id=target), json={}).status_code == 403

    def test_escalating_a_finished_instance_is_rejected(self, app, db, client, seed_tenants, auth_headers):
        role = _make_role(db, seed_tenants["a"], "Approver")
        admin = auth_headers("a", permissions=["workflow:admin", "workflow:approve"])
        _define(client, admin, [{"step_number": 1, "name": "S", "approver_type": "specific_role",
                                 "required_role_id": str(role), "escalate_to_user_id": str(uuid.uuid4())}])
        inst = _start(client, admin)
        client.post(f"/v1/workflow/instances/{inst['id']}/approve",
                    headers=auth_headers("a", permissions=["workflow:approve"], role_id=role), json={})
        assert client.post(f"/v1/workflow/instances/{inst['id']}/escalate", headers=admin, json={}).status_code == 400


class TestOverdueEscalationTask:
    def _make(self, db, client, auth_headers, tenant_id, *, auto_escalate, with_target):
        role = _make_role(db, tenant_id, f"R{uuid.uuid4().hex[:4]}")
        admin = auth_headers("a", permissions=["workflow:admin", "workflow:approve"])
        step = {"step_number": 1, "name": "S", "approver_type": "specific_role", "required_role_id": str(role),
                "timeout_hours": 1, "auto_escalate": auto_escalate}
        if with_target:
            step["escalate_to_user_id"] = str(uuid.uuid4())
        _define(client, admin, step if isinstance(step, list) else [step])
        return _start(client, admin)

    def test_overdue_auto_escalate_step_is_escalated_by_the_system(self, app, db, client, seed_tenants, auth_headers):
        from app.workflow.models import SYSTEM_ACTOR_ID
        from app.workflow import tasks

        inst = self._make(db, client, auth_headers, seed_tenants["a"], auto_escalate=True, with_target=True)
        _set_due(db, seed_tenants["a"], inst["id"], datetime.now(timezone.utc) - timedelta(minutes=5))

        result = tasks.escalate_overdue_approvals()
        assert result["escalated"] >= 1 and result["errors"] == []

        admin = auth_headers("a", permissions=["workflow:approve"])
        after = client.get(f"/v1/workflow/instances/{inst['id']}", headers=admin).get_json()
        assert after["escalated_at"] is not None
        assert after["actions"][-1]["action_type"] == "escalate"
        assert after["actions"][-1]["actor_id"] == str(SYSTEM_ACTOR_ID)

    def test_running_twice_does_not_escalate_twice(self, app, db, client, seed_tenants, auth_headers):
        from app.workflow import tasks

        inst = self._make(db, client, auth_headers, seed_tenants["a"], auto_escalate=True, with_target=True)
        _set_due(db, seed_tenants["a"], inst["id"], datetime.now(timezone.utc) - timedelta(minutes=5))
        tasks.escalate_overdue_approvals()
        second = tasks.escalate_overdue_approvals()
        assert second["escalated"] == 0

        admin = auth_headers("a", permissions=["workflow:approve"])
        actions = client.get(f"/v1/workflow/instances/{inst['id']}", headers=admin).get_json()["actions"]
        assert sum(1 for a in actions if a["action_type"] == "escalate") == 1

    def test_not_yet_due_is_left_alone(self, app, db, client, seed_tenants, auth_headers):
        from app.workflow import tasks

        inst = self._make(db, client, auth_headers, seed_tenants["a"], auto_escalate=True, with_target=True)
        tasks.escalate_overdue_approvals()
        admin = auth_headers("a", permissions=["workflow:approve"])
        assert client.get(f"/v1/workflow/instances/{inst['id']}", headers=admin).get_json()["escalated_at"] is None

    def test_overdue_without_auto_escalate_is_left_alone(self, app, db, client, seed_tenants, auth_headers):
        from app.workflow import tasks

        inst = self._make(db, client, auth_headers, seed_tenants["a"], auto_escalate=False, with_target=True)
        _set_due(db, seed_tenants["a"], inst["id"], datetime.now(timezone.utc) - timedelta(hours=3))
        tasks.escalate_overdue_approvals()
        admin = auth_headers("a", permissions=["workflow:approve"])
        assert client.get(f"/v1/workflow/instances/{inst['id']}", headers=admin).get_json()["escalated_at"] is None

    def test_auto_escalate_without_a_target_is_reported_not_escalated(self, app, db, client, seed_tenants, auth_headers):
        from app.workflow import tasks

        inst = self._make(db, client, auth_headers, seed_tenants["a"], auto_escalate=True, with_target=False)
        _set_due(db, seed_tenants["a"], inst["id"], datetime.now(timezone.utc) - timedelta(hours=3))
        result = tasks.escalate_overdue_approvals()
        assert result["skipped_no_target"] >= 1
        admin = auth_headers("a", permissions=["workflow:approve"])
        assert client.get(f"/v1/workflow/instances/{inst['id']}", headers=admin).get_json()["escalated_at"] is None


def test_escalate_task_is_in_the_beat_schedule(app):
    from app.extensions import celery

    names = {e["task"] for e in celery.conf.beat_schedule.values()}
    assert "workflow.escalate_overdue_approvals" in names
