"""Leave entitlements: days allowed vs taken vs remaining."""
from tests.test_wfm import _seed_employee


def _approve(client, h, emp, start, end, leave_type="annual"):
    lid = client.post("/v1/wfm/leave-requests", headers=h, json={
        "employee_id": str(emp), "leave_type": leave_type, "start_date": start, "end_date": end}).get_json()["id"]
    assert client.post(f"/v1/wfm/leave-requests/{lid}/decide", headers=h, json={"decision": "approved"}).status_code == 200


def _set(client, h, emp, **body):
    return client.put(f"/v1/wfm/employees/{emp}/leave-entitlements", headers=h, json=body)


class TestLeaveEntitlements:
    def test_remaining_is_entitlement_minus_taken(self, app, db, client, seed_tenants, auth_headers):
        emp = _seed_employee(db, seed_tenants["a"])
        h = auth_headers("a", permissions=["*"])
        assert _set(client, h, emp, leave_type="annual", days=21, year=2026).status_code == 200
        _approve(client, h, emp, "2026-03-02", "2026-03-06")  # 5 days

        b = client.get(f"/v1/wfm/employees/{emp}/leave-balance?year=2026", headers=h).get_json()
        assert b["year"] == 2026
        assert b["entitlements"] == {"annual": 21}
        assert b["taken"] == {"annual": 5}
        assert b["remaining"] == {"annual": 16}
        assert b["days_taken_this_year_by_type"] == {"annual": 5}

    def test_no_entitlement_means_no_remaining_figure(self, app, db, client, seed_tenants, auth_headers):
        emp = _seed_employee(db, seed_tenants["a"])
        h = auth_headers("a", permissions=["*"])
        _approve(client, h, emp, "2026-03-02", "2026-03-03", leave_type="sick")
        b = client.get(f"/v1/wfm/employees/{emp}/leave-balance?year=2026", headers=h).get_json()
        assert b["taken"] == {"sick": 2} and b["remaining"] == {} and b["entitlements"] == {}

    def test_setting_again_updates_instead_of_duplicating(self, app, db, client, seed_tenants, auth_headers):
        emp = _seed_employee(db, seed_tenants["a"])
        h = auth_headers("a", permissions=["*"])
        _set(client, h, emp, leave_type="Annual", days=20, year=2026)
        r = _set(client, h, emp, leave_type="annual", days=25, year=2026)
        assert r.status_code == 200 and r.get_json()["days"] == 25
        b = client.get(f"/v1/wfm/employees/{emp}/leave-balance?year=2026", headers=h).get_json()
        assert b["entitlements"] == {"annual": 25}

    def test_year_scoping_and_overdrawn_balance(self, app, db, client, seed_tenants, auth_headers):
        emp = _seed_employee(db, seed_tenants["a"])
        h = auth_headers("a", permissions=["*"])
        _set(client, h, emp, leave_type="annual", days=3, year=2026)
        _set(client, h, emp, leave_type="annual", days=10, year=2027)
        _approve(client, h, emp, "2026-06-01", "2026-06-05")
        b26 = client.get(f"/v1/wfm/employees/{emp}/leave-balance?year=2026", headers=h).get_json()
        b27 = client.get(f"/v1/wfm/employees/{emp}/leave-balance?year=2027", headers=h).get_json()
        assert b26["remaining"] == {"annual": -2}
        assert b27["taken"] == {} and b27["remaining"] == {"annual": 10}

    def test_validation_and_permission(self, app, db, client, seed_tenants, auth_headers):
        emp = _seed_employee(db, seed_tenants["a"])
        h = auth_headers("a", permissions=["*"])
        assert _set(client, h, emp, leave_type="annual", days=-1).status_code == 422
        assert _set(client, h, emp, leave_type="  ", days=5).status_code == 400
        only_write = auth_headers("a", permissions=["wfm:write", "wfm:read"])
        assert _set(client, only_write, emp, leave_type="annual", days=5).status_code == 403

    def test_other_tenant_cannot_set_or_see(self, app, db, client, seed_tenants, auth_headers):
        emp = _seed_employee(db, seed_tenants["a"])
        hb = auth_headers("b", permissions=["*"])
        assert _set(client, hb, emp, leave_type="annual", days=5).status_code == 404
        assert client.get(f"/v1/wfm/employees/{emp}/leave-balance", headers=hb).status_code == 404
