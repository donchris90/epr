"""EXD safety rates: TRIR/LTIFR with hours from recorded attendance."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from tests.test_wfm import _seed_employee

P1, P2 = uuid.uuid4(), uuid.uuid4()


def _dt(day, hh, mm=0):
    return datetime(2026, 10, day, hh, mm, tzinfo=timezone.utc)


def _attendance(db, tid, emp, day, cin, cout, project=P1):
    from app.modules.wfm.models import AttendanceRecord

    db.session.execute(text("SET LOCAL app.tenant_id = :t"), {"t": str(tid)})
    db.session.add(AttendanceRecord(
        tenant_id=tid, project_id=project, employee_id=emp, attendance_date=datetime(2026, 10, day).date(),
        check_in_at=cin, check_out_at=cout, capture_method="manual"))
    db.session.commit()


def _incident(db, tid, cls, day=10, project=P1):
    from app.modules.hse.models import Incident

    db.session.execute(text("SET LOCAL app.tenant_id = :t"), {"t": str(tid)})
    db.session.add(Incident(tenant_id=tid, project_id=project, classification=cls, description="x", occurred_at=_dt(day, 9)))
    db.session.commit()


def _get(client, h, **q):
    qs = "&".join(f"{k}={v}" for k, v in {"period_start": "2026-10-01", "period_end": "2026-10-31", **q}.items())
    return client.get(f"/v1/exd/safety-rates?{qs}", headers=h)


class TestSafetyRates:
    def test_rates_use_hours_from_attendance(self, app, db, client, seed_tenants, auth_headers):
        tid = seed_tenants["a"]
        emps = [_seed_employee(db, tid) for _ in range(2)]
        # 2 workers x 10 days x 8h = 160h ... use 100,000 hours scale via direct math instead:
        _attendance(db, tid, emps[0], 5, _dt(5, 7), _dt(5, 17))   # 10h
        _attendance(db, tid, emps[1], 5, _dt(5, 8), _dt(5, 18))   # 10h
        _incident(db, tid, "medical_treatment")
        _incident(db, tid, "lost_time")
        _incident(db, tid, "first_aid")  # not recordable
        h = auth_headers("a", permissions=["exd:read"])

        b = _get(client, h).get_json()
        assert b["total_hours_worked"] == "20.00"
        assert b["recordable_incidents"] == 2 and b["lost_time_incidents"] == 1
        assert float(b["trir"]) == 2 * 200000 / 20
        assert float(b["ltifr"]) == 1 * 1000000 / 20
        assert b["records_counted"] == 2 and b["records_missing_check_out"] == 0
        assert "Subcontractor" in b["hours_basis"]

    def test_no_hours_gives_null_rates_not_zero(self, app, db, client, seed_tenants, auth_headers):
        tid = seed_tenants["a"]
        _incident(db, tid, "lost_time")
        b = _get(client, auth_headers("a", permissions=["exd:read"])).get_json()
        assert b["trir"] is None and b["ltifr"] is None
        assert b["lost_time_incidents"] == 1 and b["total_hours_worked"] == "0.00"

    def test_incomplete_and_out_of_period_records_do_not_add_hours(self, app, db, client, seed_tenants, auth_headers):
        tid = seed_tenants["a"]
        emp = _seed_employee(db, tid)
        _attendance(db, tid, emp, 6, _dt(6, 7), None)          # no check-out
        _attendance(db, tid, emp, 7, _dt(7, 9), _dt(7, 8))     # backwards
        _attendance(db, tid, emp, 8, None, None)               # absence
        _attendance(db, tid, emp, 9, _dt(9, 7), _dt(9, 11))    # 4h
        h = auth_headers("a", permissions=["exd:read"])
        b = _get(client, h).get_json()
        assert b["total_hours_worked"] == "4.00" and b["records_counted"] == 1 and b["records_missing_check_out"] == 1
        assert _get(client, h, period_start="2026-11-01", period_end="2026-11-30").get_json()["total_hours_worked"] == "0.00"

    def test_project_filter(self, app, db, client, seed_tenants, auth_headers):
        tid = seed_tenants["a"]
        emp = _seed_employee(db, tid)
        _attendance(db, tid, emp, 5, _dt(5, 7), _dt(5, 15), project=P1)   # 8h
        _attendance(db, tid, emp, 6, _dt(6, 7), _dt(6, 11), project=P2)   # 4h
        _incident(db, tid, "lost_time", project=P2)
        h = auth_headers("a", permissions=["exd:read"])
        b = _get(client, h, project_id=P2).get_json()
        assert b["total_hours_worked"] == "4.00" and b["lost_time_incidents"] == 1
        assert _get(client, h, project_id=P1).get_json()["lost_time_incidents"] == 0

    def test_tenant_isolation_validation_and_permission(self, app, db, client, seed_tenants, auth_headers):
        emp = _seed_employee(db, seed_tenants["a"])
        _attendance(db, seed_tenants["a"], emp, 5, _dt(5, 7), _dt(5, 15))
        hb = auth_headers("b", permissions=["exd:read"])
        assert _get(client, hb).get_json()["total_hours_worked"] == "0.00"
        ha = auth_headers("a", permissions=["exd:read"])
        assert client.get("/v1/exd/safety-rates", headers=ha).status_code == 422
        assert _get(client, ha, period_start="2026-10-31", period_end="2026-10-01").status_code == 400
        assert _get(client, auth_headers("a", permissions=["wfm:read"])).status_code == 403
