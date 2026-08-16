"""
Tests for BDC's win_loss_summary (app/modules/bdc/services.py).

Regression coverage for a real NotImplementedError found in production
code during an audit -- unreachable from any route at the time (no
endpoint called it), but a real crash-in-waiting for anyone who wired
one, and a genuinely unimplemented documented SRS requirement (BDC-11).
"""
import uuid

from sqlalchemy import text


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def _seed_won_lost(db, tenant_id):
    from app.modules.bdc.models import Client, Opportunity, WinLossRecord

    _as_tenant(db, tenant_id)
    client_a = Client(tenant_id=tenant_id, name="Acme Construction")
    client_b = Client(tenant_id=tenant_id, name="Beta Builders")
    db.session.add_all([client_a, client_b])
    db.session.flush()

    o1 = Opportunity(tenant_id=tenant_id, client_id=client_a.id, name="Job 1", stage="won", estimated_value=5000000)
    o2 = Opportunity(tenant_id=tenant_id, client_id=client_a.id, name="Job 2", stage="won", estimated_value=15000000)
    o3 = Opportunity(tenant_id=tenant_id, client_id=client_a.id, name="Job 3", stage="lost", estimated_value=8000000)
    o4 = Opportunity(tenant_id=tenant_id, client_id=client_b.id, name="Job 4", stage="lost", estimated_value=300000000)
    db.session.add_all([o1, o2, o3, o4])
    db.session.flush()

    db.session.add_all([
        WinLossRecord(tenant_id=tenant_id, opportunity_id=o1.id, outcome="won"),
        WinLossRecord(tenant_id=tenant_id, opportunity_id=o2.id, outcome="won"),
        WinLossRecord(tenant_id=tenant_id, opportunity_id=o3.id, outcome="lost", reason_code="price"),
        WinLossRecord(tenant_id=tenant_id, opportunity_id=o4.id, outcome="lost", reason_code="price"),
    ])
    db.session.commit()


class TestWinLossSummary:
    def test_group_by_client_computes_correct_win_rate_and_value(self, app, db, client, seed_tenants, auth_headers):
        _seed_won_lost(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["bdc:read"])

        r = client.get("/v1/bdc/opportunities/win-loss-summary?group_by=client", headers=headers)
        assert r.status_code == 200
        data = {row["group_label"]: row for row in r.get_json()["data"]}

        assert data["Acme Construction"]["won"] == 2
        assert data["Acme Construction"]["lost"] == 1
        assert data["Acme Construction"]["win_rate"] == 0.6667
        assert data["Acme Construction"]["won_value"] == "20000000.0000"

        assert data["Beta Builders"]["won"] == 0
        assert data["Beta Builders"]["lost"] == 1
        assert data["Beta Builders"]["win_rate"] == 0.0

    def test_group_by_value_band_buckets_correctly(self, app, db, client, seed_tenants, auth_headers):
        _seed_won_lost(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["bdc:read"])

        r = client.get("/v1/bdc/opportunities/win-loss-summary?group_by=value_band", headers=headers)
        assert r.status_code == 200
        data = {row["group_label"]: row for row in r.get_json()["data"]}

        assert data["200M+"]["lost"] == 1  # the 300M opportunity
        assert data["10M - 50M"]["won"] == 1  # the 15M opportunity
        assert data["< 10M"]["total"] == 2  # 5M won + 8M lost

    def test_group_by_sector_returns_a_clear_error_not_a_crash(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["bdc:read"])
        r = client.get("/v1/bdc/opportunities/win-loss-summary?group_by=sector", headers=headers)
        assert r.status_code == 400
        assert "sector" in r.get_json()["detail"].lower()

    def test_invalid_group_by_returns_a_clear_error(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["bdc:read"])
        r = client.get("/v1/bdc/opportunities/win-loss-summary?group_by=nonsense", headers=headers)
        assert r.status_code == 400

    def test_cross_tenant_isolation(self, app, db, client, seed_tenants, auth_headers):
        _seed_won_lost(db, seed_tenants["a"])
        headers_b = auth_headers("b", permissions=["bdc:read"])

        r = client.get("/v1/bdc/opportunities/win-loss-summary?group_by=client", headers=headers_b)
        assert r.status_code == 200
        assert r.get_json()["data"] == []

    def test_no_data_returns_empty_list_not_an_error(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["bdc:read"])
        r = client.get("/v1/bdc/opportunities/win-loss-summary?group_by=client", headers=headers)
        assert r.status_code == 200
        assert r.get_json()["data"] == []
