"""Editing a draft workflow definition in place."""
import uuid


def _step(n=1, name="Step", user=None):
    return {"step_number": n, "name": name, "approver_type": "specific_user", "specific_user_id": str(user or uuid.uuid4())}


def _create(client, h, steps=None, **over):
    body = {"module_name": "prc", "entity_type": "purchase_request", "workflow_name": "Draft", "steps": steps or [_step()]}
    body.update(over)
    r = client.post("/v1/workflow/definitions", headers=h, json=body)
    assert r.status_code == 201
    return r.get_json()["id"]


def _get(client, h, did):
    return client.get(f"/v1/workflow/definitions/{did}", headers=h).get_json()


class TestEditDraft:
    def test_draft_is_editable_and_steps_are_replaced(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a", permissions=["workflow:admin"])
        did = _create(client, h, steps=[_step(1, "Old one"), _step(2, "Old two")])
        assert _get(client, h, did)["editable"] is True

        r = client.put(f"/v1/workflow/definitions/{did}", headers=h, json={
            "workflow_name": "Renamed", "description": "Better", "steps": [_step(1, "Only step")],
        })
        assert r.status_code == 200
        body = _get(client, h, did)
        assert body["workflow_name"] == "Renamed" and body["description"] == "Better"
        assert [s["name"] for s in body["steps"]] == ["Only step"]
        assert body["version"] == 1  # edited in place, not a new version

    def test_partial_update_leaves_steps_alone(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a", permissions=["workflow:admin"])
        did = _create(client, h, steps=[_step(1, "Keep me")])
        assert client.put(f"/v1/workflow/definitions/{did}", headers=h, json={"workflow_name": "New name"}).status_code == 200
        body = _get(client, h, did)
        assert body["workflow_name"] == "New name"
        assert [s["name"] for s in body["steps"]] == ["Keep me"]

    def test_active_definition_cannot_be_edited(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a", permissions=["workflow:admin"])
        did = _create(client, h)
        client.post(f"/v1/workflow/definitions/{did}/activate", headers=h)
        assert _get(client, h, did)["editable"] is False
        r = client.put(f"/v1/workflow/definitions/{did}", headers=h, json={"workflow_name": "x"})
        assert r.status_code == 409

    def test_definition_used_by_an_approval_stays_uneditable_after_deactivation(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a", permissions=["workflow:admin", "workflow:approve"])
        did = _create(client, h)
        client.post(f"/v1/workflow/definitions/{did}/activate", headers=h)
        r = client.post("/v1/workflow/instances", headers=h, json={
            "module_name": "prc", "entity_type": "purchase_request", "entity_id": str(uuid.uuid4()),
        })
        assert r.status_code == 201
        client.post(f"/v1/workflow/definitions/{did}/deactivate", headers=h)

        assert _get(client, h, did)["editable"] is False
        r = client.put(f"/v1/workflow/definitions/{did}", headers=h, json={"steps": [_step()]})
        assert r.status_code == 409
        assert "already been used" in (r.get_json().get("title", "") + r.get_json().get("detail", ""))

    def test_validation(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a", permissions=["workflow:admin"])
        did = _create(client, h)
        url = f"/v1/workflow/definitions/{did}"
        assert client.put(url, headers=h, json={}).status_code == 400
        assert client.put(url, headers=h, json={"steps": []}).status_code == 422
        bad = {"step_number": 1, "name": "x", "approver_type": "specific_user"}
        assert client.put(url, headers=h, json={"steps": [bad]}).status_code == 422
        # the trigger can't be changed
        assert client.put(url, headers=h, json={"module_name": "hse"}).status_code == 422
        assert [s["name"] for s in _get(client, h, did)["steps"]] == ["Step"]

    def test_permission_and_tenant_scoping(self, app, db, client, seed_tenants, auth_headers):
        ha = auth_headers("a", permissions=["workflow:admin"])
        did = _create(client, ha)
        url = f"/v1/workflow/definitions/{did}"
        assert client.put(url, headers=auth_headers("a", permissions=["workflow:approve"]), json={"workflow_name": "x"}).status_code == 403
        assert client.put(url, headers=auth_headers("b", permissions=["workflow:admin"]), json={"workflow_name": "x"}).status_code == 404
