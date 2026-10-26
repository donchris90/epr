"""Manufacturing: BOMs, production orders, completion, costing, batches."""
from decimal import Decimal


def _post(client, h, url, **body):
    return client.post(url, headers=h, json=body)


def _item(client, h, code, **extra):
    r = _post(client, h, "/v1/inv/material-items", code=code, description=code, unit="kg", **extra)
    assert r.status_code == 201, r.get_json()
    return r.get_json()["id"]


def _wh(client, h):
    r = _post(client, h, "/v1/inv/warehouses", name="Factory store", warehouse_type="central_yard")
    assert r.status_code == 201, r.get_json()
    return r.get_json()["id"]


def _stock(client, h, wh, item, qty, cost):
    r = _post(client, h, "/v1/inv/stock/receive", warehouse_id=wh, material_item_id=item, quantity=qty, unit_cost=cost)
    assert r.status_code == 201, r.get_json()


def _on_hand(client, h, wh, item):
    rows = client.get(f"/v1/inv/warehouses/{wh}/stock", headers=h).get_json()["data"]
    row = next((x for x in rows if x["material_item_id"] == item), None)
    return Decimal(row["quantity_on_hand"]) if row else Decimal(0)


def _setup(client, h, *, batch_tracked=False, scrap="0"):
    flour = _item(client, h, "FLOUR", item_type="raw_material")
    sugar = _item(client, h, "SUGAR", item_type="raw_material")
    bread = _item(client, h, "BREAD", item_type="finished_good", is_batch_tracked=batch_tracked)
    wh = _wh(client, h)
    _stock(client, h, wh, flour, 1000, 100)
    _stock(client, h, wh, sugar, 100, 500)
    r = _post(
        client, h, "/v1/mfg/boms", code="BOM-BREAD", name="Bread", product_item_id=bread, output_quantity="10",
        lines=[
            {"component_item_id": flour, "quantity": "5", "scrap_percent": scrap},
            {"component_item_id": sugar, "quantity": "1"},
        ],
    )
    assert r.status_code == 201, r.get_json()
    return {"flour": flour, "sugar": sugar, "bread": bread, "wh": wh, "bom": r.get_json()["id"]}


def _order(client, h, s, qty="20", **extra):
    r = _post(client, h, "/v1/mfg/production-orders", bom_id=s["bom"], quantity=qty, warehouse_id=s["wh"], **extra)
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def _run(client, h, oid):
    assert _post(client, h, f"/v1/mfg/production-orders/{oid}/release").status_code == 200
    assert _post(client, h, f"/v1/mfg/production-orders/{oid}/start").status_code == 200


class TestBom:
    def test_component_quantities_scale_with_scrap(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h, scrap="10")
        o = _order(client, h, s, "20")
        planned = {c["component_item_id"]: Decimal(c["planned_quantity"]) for c in o["components"]}
        assert planned[s["flour"]] == Decimal("11")  # 5 per 10 -> 10 for 20, +10% scrap
        assert planned[s["sugar"]] == Decimal("2")
        assert o["number"] == "PRD-00001" and o["status"] == "draft"

    def test_rejects_self_reference_duplicates_and_empty(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h)
        base = dict(code="X", name="X", product_item_id=s["bread"], output_quantity="1")
        assert _post(client, h, "/v1/mfg/boms", **base, lines=[{"component_item_id": s["bread"], "quantity": "1"}]).status_code == 422
        assert _post(client, h, "/v1/mfg/boms", **base, lines=[
            {"component_item_id": s["flour"], "quantity": "1"}, {"component_item_id": s["flour"], "quantity": "2"}]).status_code == 422
        assert _post(client, h, "/v1/mfg/boms", **base, lines=[]).status_code == 422
        assert _post(client, h, "/v1/mfg/boms", **base, lines=[{"component_item_id": s["flour"], "quantity": "0"}]).status_code == 422
        assert _post(client, h, "/v1/mfg/boms", code="BOM-BREAD", name="dup", product_item_id=s["bread"], output_quantity="1",
                     lines=[{"component_item_id": s["flour"], "quantity": "1"}]).status_code == 409

    def test_editing_a_bom_does_not_rewrite_an_existing_order(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h)
        o = _order(client, h, s, "10")
        r = client.put(f"/v1/mfg/boms/{s['bom']}", headers=h, json=dict(
            code="ignored", name="Bread v2", product_item_id=s["bread"], output_quantity="10",
            lines=[{"component_item_id": s["flour"], "quantity": "9"}]))
        assert r.status_code == 200 and r.get_json()["code"] == "BOM-BREAD"
        again = client.get(f"/v1/mfg/production-orders/{o['id']}", headers=h).get_json()
        assert len(again["components"]) == 2


class TestLifecycle:
    def test_state_machine(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h)
        oid = _order(client, h, s)["id"]
        assert _post(client, h, f"/v1/mfg/production-orders/{oid}/start").status_code == 409  # not released
        assert _post(client, h, f"/v1/mfg/production-orders/{oid}/complete", quantity_produced="1").status_code == 409
        _run(client, h, oid)
        assert _post(client, h, f"/v1/mfg/production-orders/{oid}/release").status_code == 409
        assert _post(client, h, f"/v1/mfg/production-orders/{oid}/cancel").get_json()["status"] == "cancelled"
        assert _post(client, h, f"/v1/mfg/production-orders/{oid}/cancel").status_code == 409

    def test_availability_shows_shortage(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h)
        oid = _order(client, h, s, "10000")["id"]  # needs 5000 flour, 1000 on hand
        rows = {r["code"]: r for r in client.get(f"/v1/mfg/production-orders/{oid}/availability", headers=h).get_json()["data"]}
        assert Decimal(rows["FLOUR"]["short"]) == Decimal("4000") and Decimal(rows["SUGAR"]["short"]) == 900


class TestCompletion:
    def test_consumes_stock_receives_goods_and_costs_the_run(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h)
        wc = _post(client, h, "/v1/mfg/work-centers", code="OVEN", name="Oven line", hourly_rate="2000").get_json()["id"]
        oid = _order(client, h, s, "20", work_center_id=wc)["id"]
        _run(client, h, oid)
        r = _post(client, h, f"/v1/mfg/production-orders/{oid}/complete", quantity_produced="20", labour_hours="3",
                  fuel_litres="10", fuel_unit_cost="900")
        assert r.status_code == 200, r.get_json()
        o = r.get_json()
        # 10 flour x 100 + 2 sugar x 500 = 2000 materials; 3h x 2000 = 6000; 10L x 900 = 9000
        assert Decimal(o["material_cost"]) == 2000 and Decimal(o["labour_cost"]) == 6000 and Decimal(o["fuel_cost"]) == 9000
        assert Decimal(o["total_cost"]) == 17000 and Decimal(o["unit_cost"]) == 850
        assert o["status"] == "done" and o["completed_at"]
        assert _on_hand(client, h, s["wh"], s["flour"]) == 990
        assert _on_hand(client, h, s["wh"], s["sugar"]) == 98
        assert _on_hand(client, h, s["wh"], s["bread"]) == 20
        stock = client.get(f"/v1/inv/warehouses/{s['wh']}/stock", headers=h).get_json()["data"]
        bread = next(x for x in stock if x["material_item_id"] == s["bread"])
        assert Decimal(bread["average_unit_cost"]) == 850

    def test_shortage_rolls_everything_back(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h)
        # 1100 units: flour (550) is available and drawn first, sugar (110 > 100) then fails
        oid = _order(client, h, s, "1100")["id"]
        _run(client, h, oid)
        r = _post(client, h, f"/v1/mfg/production-orders/{oid}/complete", quantity_produced="1100")
        assert r.status_code == 409
        # the flour had already been drawn in the same request: it must be put back
        assert _on_hand(client, h, s["wh"], s["flour"]) == 1000
        assert _on_hand(client, h, s["wh"], s["sugar"]) == 100
        assert _on_hand(client, h, s["wh"], s["bread"]) == 0
        o = client.get(f"/v1/mfg/production-orders/{oid}", headers=h).get_json()
        assert o["status"] == "in_progress" and Decimal(o["total_cost"]) == 0

    def test_scrap_is_drawn_and_its_cost_carried_by_good_units(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h)
        oid = _order(client, h, s, "20")["id"]
        _run(client, h, oid)
        o = _post(client, h, f"/v1/mfg/production-orders/{oid}/complete", quantity_produced="18", quantity_scrapped="2").get_json()
        assert Decimal(o["material_cost"]) == 2000  # full run drawn: 20 units' worth
        assert abs(Decimal(o["unit_cost"]) - Decimal("2000") / 18) < Decimal("0.0001")
        assert _on_hand(client, h, s["wh"], s["bread"]) == 18

    def test_actual_consumption_override_and_variance(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h)
        oid = _order(client, h, s, "20")["id"]
        _run(client, h, oid)
        _post(client, h, f"/v1/mfg/production-orders/{oid}/complete", quantity_produced="20",
              consumptions=[{"component_item_id": s["flour"], "consumed_quantity": "12"}])
        assert _on_hand(client, h, s["wh"], s["flour"]) == 988
        var = {v["component_item_id"]: Decimal(v["variance"]) for v in
               client.get(f"/v1/mfg/production-orders/{oid}/variances", headers=h).get_json()["data"]}
        assert var[s["flour"]] == 2 and var[s["sugar"]] == 0

    def test_override_for_a_stranger_item_is_rejected(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h)
        other = _item(client, h, "SALT")
        oid = _order(client, h, s, "10")["id"]
        _run(client, h, oid)
        r = _post(client, h, f"/v1/mfg/production-orders/{oid}/complete", quantity_produced="10",
                  consumptions=[{"component_item_id": other, "consumed_quantity": "1"}])
        assert r.status_code == 422

    def test_batch_tracked_product_requires_a_batch_and_records_quarantine(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h, batch_tracked=True)
        oid = _order(client, h, s, "10")["id"]
        _run(client, h, oid)
        assert _post(client, h, f"/v1/mfg/production-orders/{oid}/complete", quantity_produced="10").status_code == 422
        assert _on_hand(client, h, s["wh"], s["flour"]) == 1000  # the refusal did not consume anything
        o = _post(client, h, f"/v1/mfg/production-orders/{oid}/complete", quantity_produced="10",
                  batch_number="B-001", expiry_date="2027-03-01", quarantine=True).get_json()
        batches = client.get("/v1/inv/batch-numbers?status=quarantined", headers=h).get_json()["data"]
        assert len(batches) == 1 and batches[0]["batch_number"] == "B-001"
        assert batches[0]["production_order_id"] == oid and o["batch_id"] == batches[0]["id"]
        assert Decimal(batches[0]["quantity_remaining"]) == 10
        r = client.put(f"/v1/inv/batch-numbers/{batches[0]['id']}/status", headers=h, json={"status": "released"})
        assert r.status_code == 200 and r.get_json()["status"] == "released"
        assert client.put(f"/v1/inv/batch-numbers/{batches[0]['id']}/status", headers=h, json={"status": "bogus"}).status_code == 422
        assert client.get("/v1/inv/batch-numbers?status=quarantined", headers=h).get_json()["data"] == []


class TestFuelCosting:
    def _tank(self, client, h, unit="1000"):
        tank = _post(client, h, "/v1/fuel/tanks", name="Gen tank", tank_type="bulk_storage").get_json()["id"]
        _post(client, h, "/v1/fuel/purchases", tank_id=tank, quantity_litres="200", unit_price=unit, confirm_delivery=True)
        return tank

    def test_tank_fuel_is_drawn_and_priced_from_the_last_confirmed_purchase(self, app, db, client, seed_tenants, auth_headers):
        import uuid

        h = auth_headers("a")
        s = _setup(client, h)
        tank = self._tank(client, h)
        wc = _post(client, h, "/v1/mfg/work-centers", code="GEN", name="Line 1", hourly_rate="0",
                   equipment_id=str(uuid.uuid4())).get_json()["id"]
        oid = _order(client, h, s, "10", work_center_id=wc)["id"]
        _run(client, h, oid)
        o = _post(client, h, f"/v1/mfg/production-orders/{oid}/complete", quantity_produced="10",
                  fuel_litres="25", fuel_tank_id=tank).get_json()
        assert Decimal(o["fuel_cost"]) == 25000
        level = next(t for t in client.get("/v1/fuel/tanks", headers=h).get_json()["data"] if t["id"] == tank)
        assert Decimal(level["current_level_litres"]) == 175

    def test_tank_without_a_machine_is_refused_and_nothing_moves(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h)
        tank = self._tank(client, h)
        wc = _post(client, h, "/v1/mfg/work-centers", code="MAN", name="Manual", hourly_rate="0").get_json()["id"]
        oid = _order(client, h, s, "10", work_center_id=wc)["id"]
        _run(client, h, oid)
        r = _post(client, h, f"/v1/mfg/production-orders/{oid}/complete", quantity_produced="10", fuel_litres="5", fuel_tank_id=tank)
        assert r.status_code == 422
        assert _on_hand(client, h, s["wh"], s["flour"]) == 1000  # materials were rolled back too

    def test_litres_without_tank_or_price_is_refused(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h)
        oid = _order(client, h, s, "10")["id"]
        _run(client, h, oid)
        assert _post(client, h, f"/v1/mfg/production-orders/{oid}/complete", quantity_produced="10", fuel_litres="5").status_code == 422


class TestAccess:
    def test_tenant_isolation_and_permissions(self, app, db, client, seed_tenants, auth_headers):
        a = auth_headers("a")
        s = _setup(client, a)
        oid = _order(client, a, s)["id"]
        b = auth_headers("b")
        assert client.get(f"/v1/mfg/production-orders/{oid}", headers=b).status_code == 404
        assert client.get("/v1/mfg/boms", headers=b).get_json()["data"] == []
        reader = auth_headers("a", permissions=["mfg:read"])
        assert client.get("/v1/mfg/production-orders", headers=reader).status_code == 200
        assert _post(client, reader, "/v1/mfg/work-centers", code="Z", name="Z").status_code == 403
        writer = auth_headers("a", permissions=["mfg:write", "mfg:read"])
        _run(client, writer, oid)
        assert _post(client, writer, f"/v1/mfg/production-orders/{oid}/complete", quantity_produced="1").status_code == 403
