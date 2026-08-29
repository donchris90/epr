"""
Tests for QMS (Quality Management) list endpoints added while
continuing the frontend-backend gap audit: material approvals, lab
results, corrective actions, punch list items, and snag list items
all had a real POST to create a record but no GET to ever list it
again -- the same gap class already found and fixed for SUB and
Inventory earlier this session. No test file existed for this module
at all before this.
"""
import uuid


class TestMaterialApprovalsList:
    def test_real_list_returns_the_real_approval(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        client.post("/v1/qms/material-approvals", headers=headers, json={"submittal_reference": "SUB-001"})

        r = client.get("/v1/qms/material-approvals", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1
        assert r.get_json()["data"][0]["submittal_reference"] == "SUB-001"

    def test_real_list_filters_by_real_status(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        create = client.post("/v1/qms/material-approvals", headers=headers, json={"submittal_reference": "SUB-002"})
        approval_id = create.get_json()["id"]
        client.post(f"/v1/qms/material-approvals/{approval_id}/decide", headers=headers, json={"decision": "approved"})

        r = client.get("/v1/qms/material-approvals?status=approved", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1

        r2 = client.get("/v1/qms/material-approvals?status=submitted", headers=headers)
        assert len(r2.get_json()["data"]) == 0


class TestLabResultsList:
    def test_real_list_returns_the_real_result(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        client.post("/v1/qms/lab-results", headers=headers, json={"test_type": "concrete_cube_strength", "result_value": "35.5"})

        r = client.get("/v1/qms/lab-results", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1
        assert r.get_json()["data"][0]["test_type"] == "concrete_cube_strength"

    def test_real_list_filters_by_real_test_type(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        client.post("/v1/qms/lab-results", headers=headers, json={"test_type": "concrete_cube_strength"})
        client.post("/v1/qms/lab-results", headers=headers, json={"test_type": "compaction_density"})

        r = client.get("/v1/qms/lab-results?test_type=compaction_density", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1


class TestCorrectiveActionsList:
    def test_real_list_returns_the_real_action(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        client.post("/v1/qms/corrective-actions", headers=headers, json={"description": "Fix drainage issue"})

        r = client.get("/v1/qms/corrective-actions", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1

    def test_real_list_filters_by_real_ncr_id(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        ncr = client.post("/v1/qms/ncrs", headers=headers, json={"description": "Cracked slab"})
        ncr_id = ncr.get_json()["id"]
        client.post("/v1/qms/corrective-actions", headers=headers, json={"ncr_id": ncr_id, "description": "Repair slab"})
        client.post("/v1/qms/corrective-actions", headers=headers, json={"description": "Unrelated action"})

        r = client.get(f"/v1/qms/corrective-actions?ncr_id={ncr_id}", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1

    def test_real_complete_then_verify_is_a_real_full_cycle(self, app, db, client, seed_tenants, auth_headers):
        """Real, distinct two-step workflow -- completing an action and
        verifying it are two different real states (per the model's
        own docstring)."""
        headers = auth_headers("a", permissions=["*"])
        create = client.post("/v1/qms/corrective-actions", headers=headers, json={"description": "Fix drainage"})
        action_id = create.get_json()["id"]

        r1 = client.post(f"/v1/qms/corrective-actions/{action_id}/complete", headers=headers)
        assert r1.status_code == 200

        r2 = client.post(f"/v1/qms/corrective-actions/{action_id}/verify", headers=headers)
        assert r2.status_code == 200


class TestPunchListItemsList:
    def test_real_list_scoped_to_the_real_project(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        project_a = str(uuid.uuid4())
        project_b = str(uuid.uuid4())
        client.post("/v1/qms/punch-list-items", headers=headers, json={"project_id": project_a, "description": "Paint touch-up"})
        client.post("/v1/qms/punch-list-items", headers=headers, json={"project_id": project_b, "description": "Unrelated item"})

        r = client.get(f"/v1/qms/punch-list-items?project_id={project_a}", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1
        assert r.get_json()["data"][0]["description"] == "Paint touch-up"

    def test_real_close_via_the_real_endpoint(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        create = client.post("/v1/qms/punch-list-items", headers=headers, json={"project_id": str(uuid.uuid4()), "description": "Fix door"})
        item_id = create.get_json()["id"]

        r = client.post(f"/v1/qms/punch-list-items/{item_id}/close", headers=headers)
        assert r.status_code == 200
        assert r.get_json()["status"] == "closed"

        r2 = client.get(f"/v1/qms/punch-list-items?status=closed", headers=headers)
        assert len(r2.get_json()["data"]) == 1


class TestSnagListItemsList:
    def test_real_list_scoped_to_the_real_project(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        project_id = str(uuid.uuid4())
        client.post("/v1/qms/snag-list-items", headers=headers, json={"project_id": project_id, "description": "Loose tile"})

        r = client.get(f"/v1/qms/snag-list-items?project_id={project_id}", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1


class TestSensitivePermissions:
    def test_a_caller_without_qms_read_cannot_list_material_approvals(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["hse:read"])
        r = client.get("/v1/qms/material-approvals", headers=headers)
        assert r.status_code == 403

    def test_a_caller_without_qms_approve_cannot_decide_a_material_approval(self, app, db, client, seed_tenants, auth_headers):
        headers_full = auth_headers("a", permissions=["*"])
        create = client.post("/v1/qms/material-approvals", headers=headers_full, json={"submittal_reference": "SUB-003"})
        approval_id = create.get_json()["id"]

        headers_write = auth_headers("a", permissions=["qms:read", "qms:write"])
        r = client.post(f"/v1/qms/material-approvals/{approval_id}/decide", headers=headers_write, json={"decision": "approved"})
        assert r.status_code == 403

    def test_a_caller_without_qms_approve_cannot_verify_a_corrective_action(self, app, db, client, seed_tenants, auth_headers):
        headers_full = auth_headers("a", permissions=["*"])
        create = client.post("/v1/qms/corrective-actions", headers=headers_full, json={"description": "Fix issue"})
        action_id = create.get_json()["id"]

        headers_write = auth_headers("a", permissions=["qms:read", "qms:write"])
        r = client.post(f"/v1/qms/corrective-actions/{action_id}/verify", headers=headers_write)
        assert r.status_code == 403
