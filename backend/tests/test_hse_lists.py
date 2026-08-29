"""
Tests for HSE (Health, Safety & Environment) list endpoints added
while continuing the frontend-backend gap audit: near misses, toolbox
talks, PPE records, safety audits, environmental monitoring, and
waste disposal records all had a real POST to create a record but no
GET to ever list it again -- the same gap class already found and
fixed for SUB, Inventory, and QMS earlier this session.
test_hse_permit_workflow.py already covers the permit workflow; this
file focuses on the newly-closed list gaps.
"""
import uuid


class TestNearMissesList:
    def test_real_list_returns_the_real_near_miss(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        client.post("/v1/hse/near-misses", headers=headers, json={"classification": "first_aid", "description": "Slipped on wet floor"})

        r = client.get("/v1/hse/near-misses", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1
        assert r.get_json()["data"][0]["description"] == "Slipped on wet floor"

    def test_real_list_scoped_to_the_real_project(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        project_a = str(uuid.uuid4())
        client.post("/v1/hse/near-misses", headers=headers, json={"project_id": project_a, "classification": "first_aid", "description": "A"})
        client.post("/v1/hse/near-misses", headers=headers, json={"classification": "first_aid", "description": "B"})

        r = client.get(f"/v1/hse/near-misses?project_id={project_a}", headers=headers)
        assert len(r.get_json()["data"]) == 1


class TestToolboxTalksList:
    def test_real_list_returns_the_real_talk(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        client.post("/v1/hse/toolbox-talks", headers=headers, json={"topic": "Working at heights"})

        r = client.get("/v1/hse/toolbox-talks", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1
        assert r.get_json()["data"][0]["topic"] == "Working at heights"

    def test_real_add_attendee_then_sign_is_a_real_full_cycle(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        create = client.post("/v1/hse/toolbox-talks", headers=headers, json={"topic": "PPE compliance"})
        talk_id = create.get_json()["id"]

        r1 = client.post(f"/v1/hse/toolbox-talks/{talk_id}/attendees", headers=headers, json={"employee_id": str(uuid.uuid4())})
        assert r1.status_code == 201

        r2 = client.post(f"/v1/hse/toolbox-talks/{talk_id}/sign", headers=headers)
        assert r2.status_code == 200
        assert r2.get_json()["facilitator_signed"] is True


class TestPPERecordsList:
    def test_real_list_filters_by_real_employee(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        employee_id = str(uuid.uuid4())
        client.post("/v1/hse/ppe-records", headers=headers, json={"employee_id": employee_id, "ppe_type": "hard_hat"})
        client.post("/v1/hse/ppe-records", headers=headers, json={"casual_worker_id": str(uuid.uuid4()), "ppe_type": "gloves"})

        r = client.get(f"/v1/hse/ppe-records?employee_id={employee_id}", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1
        assert r.get_json()["data"][0]["ppe_type"] == "hard_hat"


class TestSafetyAuditsList:
    def test_real_list_returns_the_real_audit(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        client.post("/v1/hse/safety-audits", headers=headers, json={"audit_type": "scheduled", "score": "85.5"})

        r = client.get("/v1/hse/safety-audits", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1
        assert r.get_json()["data"][0]["score"] == "85.50"


class TestEnvironmentalMonitoringList:
    def test_real_list_filters_by_real_monitoring_type(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        client.post("/v1/hse/environmental-monitoring", headers=headers, json={"monitoring_type": "dust", "value": "50", "threshold": "40"})
        client.post("/v1/hse/environmental-monitoring", headers=headers, json={"monitoring_type": "noise", "value": "60"})

        r = client.get("/v1/hse/environmental-monitoring?monitoring_type=dust", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1
        assert r.get_json()["data"][0]["exceeds_threshold"] is True


class TestWasteDisposalList:
    def test_real_list_returns_the_real_record(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        client.post("/v1/hse/waste-disposal", headers=headers, json={"waste_type": "hazardous", "quantity": "12.5"})

        r = client.get("/v1/hse/waste-disposal", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1
        assert r.get_json()["data"][0]["waste_type"] == "hazardous"


class TestSensitivePermissions:
    def test_a_caller_without_hse_read_cannot_list_near_misses(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["qms:read"])
        r = client.get("/v1/hse/near-misses", headers=headers)
        assert r.status_code == 403

    def test_a_caller_without_hse_write_cannot_create_a_safety_audit(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["hse:read"])
        r = client.post("/v1/hse/safety-audits", headers=headers, json={"audit_type": "scheduled"})
        assert r.status_code == 403
