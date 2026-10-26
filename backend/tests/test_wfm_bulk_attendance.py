"""POST /v1/wfm/attendance/bulk"""
import uuid

from tests.test_wfm import _seed_employee

PROJECT = str(uuid.uuid4())
DAY = "2026-10-26"


def _casual(db, tid, name="Casual One"):
    from sqlalchemy import text
    from app.modules.wfm.models import CasualWorker

    db.session.execute(text("SET LOCAL app.tenant_id = :t"), {"t": str(tid)})
    w = CasualWorker(tenant_id=tid, name=name)
    db.session.add(w)
    db.session.flush()
    wid = w.id
    db.session.commit()
    return wid


def _post(client, h, rows, project=PROJECT, day=DAY):
    return client.post("/v1/wfm/attendance/bulk", headers=h, json={"project_id": project, "attendance_date": day, "rows": rows})


class TestBulkAttendance:
    def test_records_a_mixed_crew_in_one_call(self, app, db, client, seed_tenants, auth_headers):
        tid = seed_tenants["a"]
        emp, cas = _seed_employee(db, tid), _casual(db, tid)
        h = auth_headers("a", permissions=["wfm:write", "wfm:read"])
        r = _post(client, h, [
            {"employee_id": str(emp), "check_in_at": "2026-10-26T07:00:00Z", "check_out_at": "2026-10-26T16:00:00Z"},
            {"casual_worker_id": str(cas)},  # explicit absence
        ])
        assert r.status_code == 201
        b = r.get_json()
        assert (b["created"], b["skipped"], b["error"]) == (2, 0, 0)
        listed = client.get(f"/v1/wfm/attendance?project_id={PROJECT}&attendance_date={DAY}", headers=h).get_json()["data"]
        assert len(listed) == 2

    def test_partial_success_reports_each_bad_row(self, app, db, client, seed_tenants, auth_headers):
        tid = seed_tenants["a"]
        emp = _seed_employee(db, tid)
        h = auth_headers("a", permissions=["wfm:write", "wfm:read"])
        r = _post(client, h, [
            {"employee_id": str(emp), "check_in_at": "2026-10-26T07:00:00Z"},
            {"employee_id": str(uuid.uuid4())},  # unknown worker
            {},  # neither id
            {"employee_id": str(emp), "casual_worker_id": str(uuid.uuid4())},  # both
            {"employee_id": str(uuid.uuid4()), "check_in_at": "2026-10-26T09:00:00Z", "check_out_at": "2026-10-26T08:00:00Z"},
            {"employee_id": str(uuid.uuid4()), "check_out_at": "2026-10-26T08:00:00Z"},
        ])
        b = r.get_json()
        assert r.status_code == 201 and b["created"] == 1 and b["error"] == 5
        assert [x["status"] for x in b["results"]] == ["created"] + ["error"] * 5
        assert "not found" in b["results"][1]["error"]

    def test_existing_and_repeated_workers_are_skipped(self, app, db, client, seed_tenants, auth_headers):
        tid = seed_tenants["a"]
        emp = _seed_employee(db, tid)
        h = auth_headers("a", permissions=["wfm:write"])
        assert _post(client, h, [{"employee_id": str(emp)}]).status_code == 201
        again = _post(client, h, [{"employee_id": str(emp)}])
        assert again.status_code == 200 and again.get_json()["skipped"] == 1 and again.get_json()["created"] == 0
        # Same person twice in one request.
        dup = _post(client, h, [{"employee_id": str(emp)}, {"employee_id": str(emp)}], day="2026-10-27")
        assert [x["status"] for x in dup.get_json()["results"]] == ["created", "skipped"]

    def test_limits_and_permissions(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a", permissions=["wfm:write"])
        assert _post(client, h, []).status_code == 422
        assert _post(client, h, [{"employee_id": str(uuid.uuid4())}] * 201).status_code == 422
        assert _post(client, auth_headers("a", permissions=["wfm:read"]), [{"employee_id": str(uuid.uuid4())}]).status_code == 403

    def test_cannot_use_another_tenants_worker(self, app, db, client, seed_tenants, auth_headers):
        emp_b = _seed_employee(db, seed_tenants["b"])
        h = auth_headers("a", permissions=["wfm:write"])
        b = _post(client, h, [{"employee_id": str(emp_b)}]).get_json()
        assert b["created"] == 0 and b["error"] == 1
