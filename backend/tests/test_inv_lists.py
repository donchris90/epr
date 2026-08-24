"""
Tests for the real inventory list/detail endpoints added while
completing the frontend-to-backend gap audit: reservations, stock
transfers, item codes, batch numbers, serial numbers, waste records,
material returns, and stock counts all had a real POST to create a
record but no GET to ever see the list again -- confirmed directly
before adding these, matching the same gap class already found and
fixed for the SUB module earlier this session.
"""
import uuid


def _seed_warehouse_and_item(client, headers):
    wh = client.post("/v1/inv/warehouses", headers=headers, json={"name": "Lagos Yard", "warehouse_type": "site_store"})
    item = client.post("/v1/inv/material-items", headers=headers, json={"code": "MAT-001", "description": "Portland Cement 50kg", "unit": "bag"})
    return wh.get_json()["id"], item.get_json()["id"]


class TestReservationsList:
    def test_real_list_returns_the_real_reservation(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        warehouse_id, item_id = _seed_warehouse_and_item(client, headers)
        client.post("/v1/inv/stock/receive", headers=headers, json={"warehouse_id": warehouse_id, "material_item_id": item_id, "quantity": "100", "unit_cost": "5000"})
        client.post("/v1/inv/stock/reservations", headers=headers, json={"warehouse_id": warehouse_id, "material_item_id": item_id, "quantity": "10"})

        r = client.get("/v1/inv/stock/reservations", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1

    def test_real_list_filters_by_real_status(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        warehouse_id, item_id = _seed_warehouse_and_item(client, headers)
        client.post("/v1/inv/stock/receive", headers=headers, json={"warehouse_id": warehouse_id, "material_item_id": item_id, "quantity": "100", "unit_cost": "5000"})
        create = client.post("/v1/inv/stock/reservations", headers=headers, json={"warehouse_id": warehouse_id, "material_item_id": item_id, "quantity": "10"})
        client.post(f"/v1/inv/stock/reservations/{create.get_json()['id']}/release", headers=headers)

        r = client.get("/v1/inv/stock/reservations?status=active", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 0


class TestStockTransfersList:
    def test_real_list_returns_the_real_transfer(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        from_wh, item_id = _seed_warehouse_and_item(client, headers)
        to_wh = client.post("/v1/inv/warehouses", headers=headers, json={"name": "Second Yard", "warehouse_type": "site_store"}).get_json()["id"]
        client.post("/v1/inv/stock/receive", headers=headers, json={"warehouse_id": from_wh, "material_item_id": item_id, "quantity": "100", "unit_cost": "5000"})
        client.post("/v1/inv/stock-transfers", headers=headers, json={"from_warehouse_id": from_wh, "to_warehouse_id": to_wh, "material_item_id": item_id, "quantity": "20"})

        r = client.get("/v1/inv/stock-transfers", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1


class TestItemCodesList:
    def test_real_list_scoped_to_the_real_material_item(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        _, item_id = _seed_warehouse_and_item(client, headers)
        client.post("/v1/inv/item-codes", headers=headers, json={"material_item_id": item_id, "code_type": "barcode", "code_value": "1234567890"})

        r = client.get(f"/v1/inv/item-codes?material_item_id={item_id}", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1
        assert r.get_json()["data"][0]["code_value"] == "1234567890"


class TestBatchNumbersList:
    def test_real_list_returns_the_real_batch(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        warehouse_id, item_id = _seed_warehouse_and_item(client, headers)
        client.post("/v1/inv/batch-numbers", headers=headers, json={"material_item_id": item_id, "warehouse_id": warehouse_id, "batch_number": "B-001"})

        r = client.get("/v1/inv/batch-numbers", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1


class TestSerialNumbersList:
    def test_real_list_filters_by_real_status(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        _, item_id = _seed_warehouse_and_item(client, headers)
        client.post("/v1/inv/serial-numbers", headers=headers, json={"material_item_id": item_id, "serial_number": "SN-001"})

        r = client.get("/v1/inv/serial-numbers", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1
        assert r.get_json()["data"][0]["serial_number"] == "SN-001"


class TestWasteRecordsList:
    def test_real_list_returns_the_real_record(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        warehouse_id, item_id = _seed_warehouse_and_item(client, headers)
        client.post("/v1/inv/stock/receive", headers=headers, json={"warehouse_id": warehouse_id, "material_item_id": item_id, "quantity": "100", "unit_cost": "5000"})
        client.post("/v1/inv/waste-records", headers=headers, json={"warehouse_id": warehouse_id, "material_item_id": item_id, "quantity": "5", "cause_classification": "breakage"})

        r = client.get("/v1/inv/waste-records", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1


class TestMaterialReturnsList:
    def test_real_list_returns_the_real_return(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        from_wh, item_id = _seed_warehouse_and_item(client, headers)
        to_wh = client.post("/v1/inv/warehouses", headers=headers, json={"name": "Central Yard", "warehouse_type": "central_yard"}).get_json()["id"]
        client.post("/v1/inv/stock/receive", headers=headers, json={"warehouse_id": from_wh, "material_item_id": item_id, "quantity": "100", "unit_cost": "5000"})
        client.post("/v1/inv/material-returns/to-yard", headers=headers, json={"material_item_id": item_id, "source_warehouse_id": from_wh, "destination_warehouse_id": to_wh, "quantity": "10"})

        r = client.get("/v1/inv/material-returns", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1
        assert r.get_json()["data"][0]["return_type"] == "site_to_yard"


class TestStockCountsListAndDetail:
    def test_real_list_returns_the_real_count(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        warehouse_id, item_id = _seed_warehouse_and_item(client, headers)

        client.post("/v1/inv/stock-counts", headers=headers, json={"warehouse_id": warehouse_id, "count_type": "cycle", "material_item_ids": [item_id]})

        r = client.get("/v1/inv/stock-counts", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 1

    def test_real_detail_includes_the_real_lines(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        warehouse_id, item_id = _seed_warehouse_and_item(client, headers)

        created = client.post("/v1/inv/stock-counts", headers=headers, json={"warehouse_id": warehouse_id, "count_type": "cycle", "material_item_ids": [item_id]})
        count_id = created.get_json()["id"]

        r = client.get(f"/v1/inv/stock-counts/{count_id}", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["lines"]) == 1
        assert r.get_json()["lines"][0]["material_item_id"] == item_id

    def test_real_detail_404s_for_a_nonexistent_count(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["*"])
        r = client.get(f"/v1/inv/stock-counts/{uuid.uuid4()}", headers=headers)
        assert r.status_code == 404


class TestSensitivePermissions:
    def test_a_caller_without_inv_read_cannot_list_reservations(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["hse:read"])
        r = client.get("/v1/inv/stock/reservations", headers=headers)
        assert r.status_code == 403

    def test_a_caller_without_inv_approve_cannot_apply_a_stock_count_adjustment(self, app, db, client, seed_tenants, auth_headers):
        headers_full = auth_headers("a", permissions=["*"])
        warehouse_id, item_id = _seed_warehouse_and_item(client, headers_full)
        created = client.post("/v1/inv/stock-counts", headers=headers_full, json={"warehouse_id": warehouse_id, "count_type": "cycle", "material_item_ids": [item_id]})
        count_id = created.get_json()["id"]
        client.post(f"/v1/inv/stock-counts/{count_id}/complete", headers=headers_full)

        headers_write = auth_headers("a", permissions=["inv:read", "inv:write"])
        r = client.post(f"/v1/inv/stock-counts/{count_id}/apply-adjustment", headers=headers_write)
        assert r.status_code == 403
