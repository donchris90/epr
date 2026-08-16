"""
Tests for app/notifications/ and its real integration into the
Workflow Engine (app/workflow/services.py).
"""
import uuid

from sqlalchemy import text


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


class TestNotificationsService:
    def test_notify_creates_a_real_notification(self, app, db, seed_tenants):
        from app.notifications import services

        _as_tenant(db, seed_tenants["a"])
        user_id = uuid.uuid4()
        n = services.notify(
            seed_tenants["a"], user_id=user_id, type="test.event", title="Test", body="A body",
        )
        db.session.flush()
        notification_id = n.id
        read_at = n.read_at
        db.session.commit()

        assert notification_id is not None
        assert read_at is None

    def test_list_for_user_only_returns_that_users_notifications(self, app, db, client, seed_tenants, auth_headers):
        from app.notifications import services

        user_a, user_b = uuid.uuid4(), uuid.uuid4()
        _as_tenant(db, seed_tenants["a"])
        services.notify(seed_tenants["a"], user_id=user_a, type="test.event", title="For A")
        services.notify(seed_tenants["a"], user_id=user_b, type="test.event", title="For B")
        db.session.commit()

        headers = auth_headers("a", user_id=user_a)
        r = client.get("/v1/notifications", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1
        assert r.get_json()["data"][0]["title"] == "For A"

    def test_mark_read_updates_unread_count(self, app, db, client, seed_tenants, auth_headers):
        from app.notifications import services

        user_id = uuid.uuid4()
        _as_tenant(db, seed_tenants["a"])
        services.notify(seed_tenants["a"], user_id=user_id, type="test.event", title="Test")
        db.session.commit()

        headers = auth_headers("a", user_id=user_id)
        r = client.get("/v1/notifications/unread-count", headers=headers)
        assert r.get_json()["unread_count"] == 1

        notif_id = client.get("/v1/notifications", headers=headers).get_json()["data"][0]["id"]
        client.post(f"/v1/notifications/{notif_id}/read", headers=headers)

        r = client.get("/v1/notifications/unread-count", headers=headers)
        assert r.get_json()["unread_count"] == 0

    def test_cannot_mark_another_users_notification_read(self, app, db, client, seed_tenants, auth_headers):
        from app.notifications import services

        user_a, user_b = uuid.uuid4(), uuid.uuid4()
        _as_tenant(db, seed_tenants["a"])
        n = services.notify(seed_tenants["a"], user_id=user_a, type="test.event", title="For A")
        db.session.flush()
        notif_id = n.id
        db.session.commit()

        headers_b = auth_headers("a", user_id=user_b)
        r = client.post(f"/v1/notifications/{notif_id}/read", headers=headers_b)
        assert r.status_code == 404

    def test_cross_tenant_isolation(self, app, db, client, seed_tenants, auth_headers):
        from app.notifications import services

        user_id = uuid.uuid4()
        _as_tenant(db, seed_tenants["a"])
        services.notify(seed_tenants["a"], user_id=user_id, type="test.event", title="Tenant A's notification")
        db.session.commit()

        # Same user_id, but requesting under tenant B's JWT -- must see nothing.
        headers_b = auth_headers("b", user_id=user_id)
        r = client.get("/v1/notifications", headers=headers_b)
        assert len(r.get_json()["data"]) == 0


class TestWorkflowNotificationIntegration:
    """The real integration: starting/advancing/rejecting a workflow
    instance actually creates real notifications, not just an
    unused capability sitting next to the engine."""

    def _make_role(self, db, tenant_id, name):
        from app.models.core import Role

        _as_tenant(db, tenant_id)
        role = Role(tenant_id=tenant_id, name=name, permission_set=["workflow:approve"])
        db.session.add(role)
        db.session.flush()
        role_id = role.id
        db.session.commit()
        return role_id

    def test_starting_an_instance_notifies_the_first_steps_approvers(self, app, db, client, seed_tenants, auth_headers):
        finance_role_id = self._make_role(db, seed_tenants["a"], "Finance")
        admin_headers = auth_headers("a", permissions=["workflow:admin", "workflow:approve"])

        r = client.post("/v1/workflow/definitions", headers=admin_headers, json={
            "module_name": "prc", "entity_type": "purchase_request", "workflow_name": "Notif Integration Test",
            "steps": [{"step_number": 1, "name": "Finance", "approver_type": "specific_role", "required_role_id": str(finance_role_id)}],
        })
        definition_id = r.get_json()["id"]
        client.post(f"/v1/workflow/definitions/{definition_id}/activate", headers=admin_headers)

        # Role-based notification resolution queries the real `users`
        # table for anyone holding this role -- a JWT claim alone
        # (what auth_headers builds) isn't enough, a real User row is
        # needed for the query to find them.
        from app.models.core import User

        _as_tenant(db, seed_tenants["a"])
        finance_user = User(tenant_id=seed_tenants["a"], email="finance@notiftest.com", password_hash="x", role_id=finance_role_id, status="active")
        db.session.add(finance_user)
        db.session.flush()
        finance_user_id = finance_user.id
        db.session.commit()

        finance_headers = auth_headers("a", permissions=["workflow:approve"], role_id=finance_role_id, user_id=finance_user_id)

        client.post("/v1/workflow/instances", headers=admin_headers, json={
            "module_name": "prc", "entity_type": "purchase_request", "entity_id": str(uuid.uuid4()), "amount": "500000",
        })

        r = client.get("/v1/notifications", headers=finance_headers)
        assert len(r.get_json()["data"]) == 1
        assert r.get_json()["data"][0]["type"] == "workflow.approval_requested"

    def test_full_approval_notifies_the_initiator(self, app, db, client, seed_tenants, auth_headers):
        finance_role_id = self._make_role(db, seed_tenants["a"], "Finance")
        initiator_id = uuid.uuid4()
        admin_headers = auth_headers("a", permissions=["workflow:admin", "workflow:approve"], user_id=initiator_id)

        r = client.post("/v1/workflow/definitions", headers=admin_headers, json={
            "module_name": "prc", "entity_type": "purchase_request", "workflow_name": "Notif Approval Test",
            "steps": [{"step_number": 1, "name": "Finance", "approver_type": "specific_role", "required_role_id": str(finance_role_id)}],
        })
        definition_id = r.get_json()["id"]
        client.post(f"/v1/workflow/definitions/{definition_id}/activate", headers=admin_headers)

        r = client.post("/v1/workflow/instances", headers=admin_headers, json={
            "module_name": "prc", "entity_type": "purchase_request", "entity_id": str(uuid.uuid4()), "amount": "500000",
        })
        instance_id = r.get_json()["id"]

        finance_headers = auth_headers("a", permissions=["workflow:approve"], role_id=finance_role_id)
        client.post(f"/v1/workflow/instances/{instance_id}/approve", headers=finance_headers, json={})

        r = client.get("/v1/notifications", headers=admin_headers)
        types = [n["type"] for n in r.get_json()["data"]]
        assert "workflow.instance_approved" in types

    def test_rejection_notifies_the_initiator(self, app, db, client, seed_tenants, auth_headers):
        finance_role_id = self._make_role(db, seed_tenants["a"], "Finance")
        initiator_id = uuid.uuid4()
        admin_headers = auth_headers("a", permissions=["workflow:admin", "workflow:approve"], user_id=initiator_id)

        r = client.post("/v1/workflow/definitions", headers=admin_headers, json={
            "module_name": "prc", "entity_type": "purchase_request", "workflow_name": "Notif Rejection Test",
            "steps": [{"step_number": 1, "name": "Finance", "approver_type": "specific_role", "required_role_id": str(finance_role_id)}],
        })
        definition_id = r.get_json()["id"]
        client.post(f"/v1/workflow/definitions/{definition_id}/activate", headers=admin_headers)

        r = client.post("/v1/workflow/instances", headers=admin_headers, json={
            "module_name": "prc", "entity_type": "purchase_request", "entity_id": str(uuid.uuid4()), "amount": "500000",
        })
        instance_id = r.get_json()["id"]

        finance_headers = auth_headers("a", permissions=["workflow:approve"], role_id=finance_role_id)
        client.post(f"/v1/workflow/instances/{instance_id}/reject", headers=finance_headers, json={"comment": "No"})

        r = client.get("/v1/notifications", headers=admin_headers)
        types = [n["type"] for n in r.get_json()["data"]]
        assert "workflow.instance_rejected" in types
