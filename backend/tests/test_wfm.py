"""
Tests for WFM (Workforce Management) -- no test file existed for this
module before this batch. Prioritizes the critical, explicitly-
required fix (payroll must only ever consume approved/locked
timesheets) and permission gating around sensitive employee/payroll
data, per this batch's own explicit instruction.
"""
import uuid

from sqlalchemy import text


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def _seed_employee(db, tenant_id, *, name="Test Employee", monthly_rate="500000"):
    from app.modules.wfm.models import Employee

    _as_tenant(db, tenant_id)
    employee = Employee(tenant_id=tenant_id, name=name, employment_type="permanent", monthly_rate=monthly_rate, status="active")
    db.session.add(employee)
    db.session.flush()
    employee_id = employee.id
    db.session.commit()
    return employee_id


def _seed_timesheet(db, tenant_id, *, employee_id, status="pending_approval", period_start="2026-08-01", period_end="2026-08-31", hours="160", rate="3000"):
    from app.modules.wfm.models import Timesheet

    _as_tenant(db, tenant_id)
    ts = Timesheet(
        tenant_id=tenant_id, employee_id=employee_id, project_id=uuid.uuid4(),
        period_start=period_start, period_end=period_end, pay_basis="time_based",
        hours_or_units=hours, rate_applied=rate, gross_amount=str(float(hours) * float(rate)),
        status=status,
    )
    db.session.add(ts)
    db.session.flush()
    ts_id = ts.id
    db.session.commit()
    return ts_id


class TestPayrollRunsList:
    def test_real_list_returns_every_real_run_with_bank_account_ref_exposed(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"])
        _seed_timesheet(db, seed_tenants["a"], employee_id=emp_id, status="approved", period_start="2026-08-01", period_end="2026-08-31")

        headers = auth_headers("a", permissions=["*"])
        client.post("/v1/wfm/payroll-runs", headers=headers, json={"period_start": "2026-08-01", "period_end": "2026-08-31"})

        r = client.get("/v1/wfm/payroll-runs", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1
        line = r.get_json()["data"][0]["lines"][0]
        assert "bank_account_ref" in line


class TestPayrollOnlyConsumesApprovedOrLockedTimesheets:
    """The single most important requirement of this batch, tested
    directly and explicitly -- not just implied by other tests."""

    def test_a_pending_approval_timesheet_is_never_pulled_into_payroll(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"])
        _seed_timesheet(db, seed_tenants["a"], employee_id=emp_id, status="pending_approval")

        headers = auth_headers("a", permissions=["*"])
        r = client.post("/v1/wfm/payroll-runs", headers=headers, json={"period_start": "2026-08-01", "period_end": "2026-08-31"})
        assert r.status_code == 201
        assert float(r.get_json()["total_gross"]) == 0

    def test_a_rejected_timesheet_is_never_pulled_into_payroll(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"])
        _seed_timesheet(db, seed_tenants["a"], employee_id=emp_id, status="rejected")

        headers = auth_headers("a", permissions=["*"])
        r = client.post("/v1/wfm/payroll-runs", headers=headers, json={"period_start": "2026-08-01", "period_end": "2026-08-31"})
        assert float(r.get_json()["total_gross"]) == 0

    def test_a_returned_timesheet_is_never_pulled_into_payroll(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"])
        _seed_timesheet(db, seed_tenants["a"], employee_id=emp_id, status="returned")

        headers = auth_headers("a", permissions=["*"])
        r = client.post("/v1/wfm/payroll-runs", headers=headers, json={"period_start": "2026-08-01", "period_end": "2026-08-31"})
        assert float(r.get_json()["total_gross"]) == 0

    def test_a_real_approved_timesheet_is_correctly_included_in_payroll(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"])
        _seed_timesheet(db, seed_tenants["a"], employee_id=emp_id, status="approved", hours="160", rate="3000")

        headers = auth_headers("a", permissions=["*"])
        r = client.post("/v1/wfm/payroll-runs", headers=headers, json={"period_start": "2026-08-01", "period_end": "2026-08-31"})
        assert float(r.get_json()["total_gross"]) == 480000.0

    def test_a_real_locked_timesheet_is_correctly_included_in_payroll(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"])
        _seed_timesheet(db, seed_tenants["a"], employee_id=emp_id, status="locked", hours="160", rate="3000")

        headers = auth_headers("a", permissions=["*"])
        r = client.post("/v1/wfm/payroll-runs", headers=headers, json={"period_start": "2026-08-01", "period_end": "2026-08-31"})
        assert float(r.get_json()["total_gross"]) == 480000.0

    def test_a_real_mix_only_sums_the_real_approved_and_locked_ones(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"])
        _seed_timesheet(db, seed_tenants["a"], employee_id=emp_id, status="approved", hours="100", rate="1000")
        _seed_timesheet(db, seed_tenants["a"], employee_id=emp_id, status="locked", hours="50", rate="1000")
        _seed_timesheet(db, seed_tenants["a"], employee_id=emp_id, status="pending_approval", hours="9999", rate="9999")
        _seed_timesheet(db, seed_tenants["a"], employee_id=emp_id, status="rejected", hours="9999", rate="9999")

        headers = auth_headers("a", permissions=["*"])
        r = client.post("/v1/wfm/payroll-runs", headers=headers, json={"period_start": "2026-08-01", "period_end": "2026-08-31"})
        assert float(r.get_json()["total_gross"]) == 150000.0


class TestTimesheetLifecycle:
    def test_lock_requires_a_real_approved_timesheet(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"])
        ts_id = _seed_timesheet(db, seed_tenants["a"], employee_id=emp_id, status="pending_approval")

        headers = auth_headers("a", permissions=["*"])
        r = client.post(f"/v1/wfm/timesheets/{ts_id}/lock", headers=headers)
        assert r.status_code == 409

    def test_lock_succeeds_on_a_real_approved_timesheet(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"])
        ts_id = _seed_timesheet(db, seed_tenants["a"], employee_id=emp_id, status="approved")

        headers = auth_headers("a", permissions=["*"])
        r = client.post(f"/v1/wfm/timesheets/{ts_id}/lock", headers=headers)
        assert r.status_code == 200
        assert r.get_json()["status"] == "locked"

    def test_return_for_correction_then_resubmit_is_a_real_full_cycle(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"])
        ts_id = _seed_timesheet(db, seed_tenants["a"], employee_id=emp_id, status="pending_approval")

        headers = auth_headers("a", permissions=["*"])
        r1 = client.post(f"/v1/wfm/timesheets/{ts_id}/return", headers=headers)
        assert r1.status_code == 200
        assert r1.get_json()["status"] == "returned"

        r2 = client.post(f"/v1/wfm/timesheets/{ts_id}/resubmit", headers=headers)
        assert r2.status_code == 200
        assert r2.get_json()["status"] == "pending_approval"

    def test_edit_is_blocked_on_a_real_approved_timesheet(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"])
        ts_id = _seed_timesheet(db, seed_tenants["a"], employee_id=emp_id, status="approved")

        headers = auth_headers("a", permissions=["*"])
        r = client.put(f"/v1/wfm/timesheets/{ts_id}", headers=headers, json={"hours_or_units": "999"})
        assert r.status_code == 409

    def test_edit_succeeds_on_a_real_pending_timesheet_and_recomputes_gross(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"])
        ts_id = _seed_timesheet(db, seed_tenants["a"], employee_id=emp_id, status="pending_approval", hours="100", rate="1000")

        headers = auth_headers("a", permissions=["*"])
        r = client.put(f"/v1/wfm/timesheets/{ts_id}", headers=headers, json={"hours_or_units": "50"})
        assert r.status_code == 200
        assert float(r.get_json()["gross_amount"]) == 50000.0

    def test_real_detail_endpoint_returns_the_real_full_timesheet(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"])
        ts_id = _seed_timesheet(db, seed_tenants["a"], employee_id=emp_id, hours="42", rate="500")

        headers = auth_headers("a", permissions=["*"])
        r = client.get(f"/v1/wfm/timesheets/{ts_id}", headers=headers)
        assert r.status_code == 200
        assert float(r.get_json()["hours_or_units"]) == 42.0
        assert float(r.get_json()["rate_applied"]) == 500.0


class TestEmployeeLifecycle:
    def test_real_detail_endpoint_returns_the_real_employee(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"], name="Chidi Okafor")

        headers = auth_headers("a", permissions=["*"])
        r = client.get(f"/v1/wfm/employees/{emp_id}", headers=headers)
        assert r.status_code == 200
        assert r.get_json()["name"] == "Chidi Okafor"

    def test_real_update_changes_only_the_real_provided_fields(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"], name="Original Name")

        headers = auth_headers("a", permissions=["*"])
        r = client.put(f"/v1/wfm/employees/{emp_id}", headers=headers, json={"role": "Site Supervisor"})
        assert r.status_code == 200
        assert r.get_json()["role"] == "Site Supervisor"
        assert r.get_json()["name"] == "Original Name"

    def test_real_terminate_then_reactivate_is_a_real_full_cycle(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"])

        headers = auth_headers("a", permissions=["*"])
        r1 = client.post(f"/v1/wfm/employees/{emp_id}/terminate", headers=headers)
        assert r1.status_code == 200
        assert r1.get_json()["status"] == "inactive"

        r2 = client.post(f"/v1/wfm/employees/{emp_id}/reactivate", headers=headers)
        assert r2.status_code == 200
        assert r2.get_json()["status"] == "active"

    def test_cannot_terminate_an_already_terminated_employee(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["*"])
        client.post(f"/v1/wfm/employees/{emp_id}/terminate", headers=headers)

        r = client.post(f"/v1/wfm/employees/{emp_id}/terminate", headers=headers)
        assert r.status_code == 409

    def test_real_assign_project_is_idempotent(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"])
        project_id = str(uuid.uuid4())
        headers = auth_headers("a", permissions=["*"])

        r1 = client.post(f"/v1/wfm/employees/{emp_id}/assign-project", headers=headers, json={"project_id": project_id})
        assert project_id in r1.get_json()["assigned_project_ids"]

        r2 = client.post(f"/v1/wfm/employees/{emp_id}/assign-project", headers=headers, json={"project_id": project_id})
        assert r2.get_json()["assigned_project_ids"].count(project_id) == 1

    def test_real_transfer_project_moves_the_real_assignment(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"])
        old_project = str(uuid.uuid4())
        new_project = str(uuid.uuid4())
        headers = auth_headers("a", permissions=["*"])
        client.post(f"/v1/wfm/employees/{emp_id}/assign-project", headers=headers, json={"project_id": old_project})

        r = client.post(f"/v1/wfm/employees/{emp_id}/transfer-project", headers=headers, json={"from_project_id": old_project, "to_project_id": new_project})
        assert old_project not in r.get_json()["assigned_project_ids"]
        assert new_project in r.get_json()["assigned_project_ids"]


class TestLeave:
    def test_real_list_filters_by_real_employee(self, app, db, client, seed_tenants, auth_headers):
        emp_a = _seed_employee(db, seed_tenants["a"], name="A")
        emp_b = _seed_employee(db, seed_tenants["a"], name="B")
        headers = auth_headers("a", permissions=["*"])
        client.post("/v1/wfm/leave-requests", headers=headers, json={"employee_id": str(emp_a), "leave_type": "annual", "start_date": "2026-09-01", "end_date": "2026-09-05"})
        client.post("/v1/wfm/leave-requests", headers=headers, json={"employee_id": str(emp_b), "leave_type": "annual", "start_date": "2026-09-01", "end_date": "2026-09-05"})

        r = client.get(f"/v1/wfm/leave-requests?employee_id={emp_a}", headers=headers)
        assert len(r.get_json()["data"]) == 1

    def test_real_cancel_works_on_a_real_pending_or_approved_request(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["*"])
        create = client.post("/v1/wfm/leave-requests", headers=headers, json={"employee_id": str(emp_id), "leave_type": "annual", "start_date": "2026-09-01", "end_date": "2026-09-05"})
        leave_id = create.get_json()["id"]

        r = client.post(f"/v1/wfm/leave-requests/{leave_id}/cancel", headers=headers)
        assert r.status_code == 200
        assert r.get_json()["status"] == "cancelled"

    def test_real_balance_sums_real_approved_days_this_year_by_type(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["*"])
        create = client.post("/v1/wfm/leave-requests", headers=headers, json={"employee_id": str(emp_id), "leave_type": "annual", "start_date": "2026-09-01", "end_date": "2026-09-05"})
        leave_id = create.get_json()["id"]
        client.post(f"/v1/wfm/leave-requests/{leave_id}/decide", headers=headers, json={"decision": "approved"})

        r = client.get(f"/v1/wfm/employees/{emp_id}/leave-balance", headers=headers)
        assert r.status_code == 200
        assert r.get_json()["days_taken_this_year_by_type"]["annual"] == 5


class TestAttendance:
    def test_real_mark_absent_creates_a_real_record_with_no_check_in(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"])
        project_id = str(uuid.uuid4())
        headers = auth_headers("a", permissions=["*"])

        r = client.post("/v1/wfm/attendance/mark-absent", headers=headers, json={"project_id": project_id, "attendance_date": "2026-08-24", "employee_id": str(emp_id)})
        assert r.status_code == 201
        assert r.get_json()["check_in_at"] is None

    def test_real_mark_absent_rejects_a_real_duplicate_for_the_same_person_and_day(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"])
        project_id = str(uuid.uuid4())
        headers = auth_headers("a", permissions=["*"])
        client.post("/v1/wfm/attendance/mark-absent", headers=headers, json={"project_id": project_id, "attendance_date": "2026-08-24", "employee_id": str(emp_id)})

        r = client.post("/v1/wfm/attendance/mark-absent", headers=headers, json={"project_id": project_id, "attendance_date": "2026-08-24", "employee_id": str(emp_id)})
        assert r.status_code == 409

    def test_real_correction_updates_the_real_check_in_and_out_times(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"])
        project_id = str(uuid.uuid4())
        headers = auth_headers("a", permissions=["*"])
        created = client.post("/v1/wfm/attendance", headers=headers, json={"project_id": project_id, "employee_id": str(emp_id), "attendance_date": "2026-08-24"})
        record_id = created.get_json()["id"]

        r = client.put(f"/v1/wfm/attendance/{record_id}", headers=headers, json={"check_in_at": "2026-08-24T07:00:00Z", "check_out_at": "2026-08-24T16:00:00Z"})
        assert r.status_code == 200
        assert r.get_json()["check_in_at"] is not None

    def test_real_list_filters_by_real_project(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"])
        project_a = str(uuid.uuid4())
        project_b = str(uuid.uuid4())
        headers = auth_headers("a", permissions=["*"])
        client.post("/v1/wfm/attendance", headers=headers, json={"project_id": project_a, "employee_id": str(emp_id), "attendance_date": "2026-08-24"})
        client.post("/v1/wfm/attendance", headers=headers, json={"project_id": project_b, "employee_id": str(emp_id), "attendance_date": "2026-08-24"})

        r = client.get(f"/v1/wfm/attendance?project_id={project_a}", headers=headers)
        assert len(r.get_json()["data"]) == 1


class TestSensitivePermissions:
    """This batch's own explicit instruction: test permissions
    carefully because employee/payroll information is sensitive."""

    def test_a_caller_without_wfm_read_cannot_list_employees(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["hse:read"])
        r = client.get("/v1/wfm/employees", headers=headers)
        assert r.status_code == 403

    def test_a_caller_without_wfm_approve_cannot_terminate_an_employee(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["wfm:read", "wfm:write"])
        r = client.post(f"/v1/wfm/employees/{emp_id}/terminate", headers=headers)
        assert r.status_code == 403

    def test_a_caller_without_wfm_approve_cannot_finalize_payroll(self, app, db, client, seed_tenants, auth_headers):
        headers_write = auth_headers("a", permissions=["wfm:write"])
        r = client.post("/v1/wfm/payroll-runs", headers=headers_write, json={"period_start": "2026-08-01", "period_end": "2026-08-31"})
        assert r.status_code == 403

    def test_a_caller_without_wfm_medical_cannot_read_medical_records_even_with_broad_wfm_access(self, app, db, client, seed_tenants, auth_headers):
        """Business rule already established in this module (routes.py's
        own docstring): a real, distinct permission gate on top of
        general wfm:* access."""
        emp_id = _seed_employee(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["wfm:read", "wfm:write", "wfm:approve"])
        r = client.get(f"/v1/wfm/employees/{emp_id}/medical-records", headers=headers)
        assert r.status_code == 403

    def test_a_caller_with_wfm_medical_can_read_medical_records(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["wfm:medical"])
        r = client.get(f"/v1/wfm/employees/{emp_id}/medical-records", headers=headers)
        assert r.status_code == 200

    def test_attendance_correction_requires_the_real_elevated_wfm_approve_grant(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"])
        headers_write = auth_headers("a", permissions=["wfm:read", "wfm:write"])
        created = client.post("/v1/wfm/attendance", headers=headers_write, json={"project_id": str(uuid.uuid4()), "employee_id": str(emp_id), "attendance_date": "2026-08-24"})
        record_id = created.get_json()["id"]

        r = client.put(f"/v1/wfm/attendance/{record_id}", headers=headers_write, json={"check_in_at": "2026-08-24T07:00:00Z"})
        assert r.status_code == 403

    def test_cross_tenant_isolation_on_employee_detail(self, app, db, client, seed_tenants, auth_headers):
        emp_id = _seed_employee(db, seed_tenants["a"])
        headers_b = auth_headers("b", permissions=["*"])
        r = client.get(f"/v1/wfm/employees/{emp_id}", headers=headers_b)
        assert r.status_code == 404
