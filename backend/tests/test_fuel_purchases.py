"""Fuel purchases: a purchase only changes the tank once its delivery is confirmed."""
from decimal import Decimal


def _tank(client, h, name="Tank A"):
    r = client.post("/v1/fuel/tanks", headers=h, json={"name": name, "tank_type": "bulk_storage"})
    assert r.status_code == 201
    return r.get_json()["id"]


def _level(client, h, tank_id):
    rows = client.get("/v1/fuel/tanks", headers=h).get_json()["data"]
    return Decimal(next(t for t in rows if t["id"] == tank_id)["current_level_litres"])


def _buy(client, h, tank_id, qty="500", **extra):
    return client.post("/v1/fuel/purchases", headers=h, json={"tank_id": tank_id, "quantity_litres": qty, "unit_price": "900", **extra})


class TestPendingPurchases:
    def test_unconfirmed_purchase_leaves_the_tank_at_zero_and_is_listed_as_pending(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a", permissions=["*"])
        tank = _tank(client, h)
        assert _buy(client, h, tank).status_code == 201
        assert _level(client, h, tank) == 0
        pending = client.get("/v1/fuel/purchases?confirmed=false", headers=h).get_json()["data"]
        assert len(pending) == 1 and pending[0]["quantity_litres"] == "500.00" and pending[0]["delivery_confirmed"] is False

    def test_confirming_adds_to_the_tank_once(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a", permissions=["*"])
        tank = _tank(client, h)
        pid = _buy(client, h, tank).get_json()["id"]
        r = client.post(f"/v1/fuel/purchases/{pid}/confirm-delivery", headers=h)
        assert r.status_code == 200 and r.get_json()["delivery_confirmed"] is True
        assert _level(client, h, tank) == 500
        assert client.post(f"/v1/fuel/purchases/{pid}/confirm-delivery", headers=h).status_code == 409
        assert _level(client, h, tank) == 500  # not double counted
        assert client.get("/v1/fuel/purchases?confirmed=false", headers=h).get_json()["data"] == []
        assert len(client.get("/v1/fuel/purchases?confirmed=true", headers=h).get_json()["data"]) == 1

    def test_recording_as_already_delivered_updates_the_tank_immediately(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a", permissions=["*"])
        tank = _tank(client, h)
        r = _buy(client, h, tank, confirm_delivery=True)
        assert r.status_code == 201
        body = r.get_json()
        assert body["delivery_confirmed"] is True and body["delivered_at"] is not None
        assert _level(client, h, tank) == 500
        assert client.get("/v1/fuel/purchases?confirmed=false", headers=h).get_json()["data"] == []

    def test_levels_add_up_across_purchases(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a", permissions=["*"])
        tank = _tank(client, h)
        _buy(client, h, tank, "500", confirm_delivery=True)
        pid = _buy(client, h, tank, "250.5").get_json()["id"]
        assert _level(client, h, tank) == 500
        client.post(f"/v1/fuel/purchases/{pid}/confirm-delivery", headers=h)
        assert _level(client, h, tank) == Decimal("750.50")

    def test_a_recorded_purchase_for_an_unknown_tank_is_404_and_stores_nothing(self, app, db, client, seed_tenants, auth_headers):
        import uuid

        h = auth_headers("a", permissions=["*"])
        assert _buy(client, h, str(uuid.uuid4()), confirm_delivery=True).status_code == 404
        assert client.get("/v1/fuel/purchases", headers=h).get_json()["data"] == []

    def test_filters_and_validation(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a", permissions=["*"])
        t1, t2 = _tank(client, h, "T1"), _tank(client, h, "T2")
        _buy(client, h, t1)
        _buy(client, h, t2)
        assert len(client.get(f"/v1/fuel/purchases?tank_id={t1}", headers=h).get_json()["data"]) == 1
        assert len(client.get("/v1/fuel/purchases", headers=h).get_json()["data"]) == 2
        assert client.get("/v1/fuel/purchases?confirmed=maybe", headers=h).status_code == 400

    def test_permissions_and_tenant_isolation(self, app, db, client, seed_tenants, auth_headers):
        ha = auth_headers("a", permissions=["*"])
        tank = _tank(client, ha)
        pid = _buy(client, ha, tank).get_json()["id"]
        assert client.get("/v1/fuel/purchases", headers=auth_headers("a", permissions=["inv:read"])).status_code == 403
        hb = auth_headers("b", permissions=["*"])
        assert client.get("/v1/fuel/purchases", headers=hb).get_json()["data"] == []
        assert client.post(f"/v1/fuel/purchases/{pid}/confirm-delivery", headers=hb).status_code == 404
        assert _level(client, ha, tank) == 0
