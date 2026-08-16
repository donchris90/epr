"""
Tests for the real PRC-to-Inventory integration
(app/modules/prc/services.py:confirm_goods_receipt).

Regression coverage for a real, stale gap found in a production-
hardening audit: confirm_goods_receipt's own comment said "once
Module 8 (Inventory) exists" -- but Module 8 has existed since early
in this build. Confirming a GRN never actually updated real Inventory
stock until this fix.
"""
import uuid

from sqlalchemy import text


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def _seed_vendor_warehouse_material(db, tenant_id):
    from app.modules.prc.models import Vendor
    from app.modules.inv.models import Warehouse, MaterialItem

    _as_tenant(db, tenant_id)
    vendor = Vendor(tenant_id=tenant_id, name="Test Vendor")
    warehouse = Warehouse(tenant_id=tenant_id, name="Test Warehouse", warehouse_type="site_store")
    material = MaterialItem(tenant_id=tenant_id, code=f"MAT-{uuid.uuid4()}", description="Test Material", unit="unit")
    db.session.add_all([vendor, warehouse, material])
    db.session.flush()
    ids = (vendor.id, warehouse.id, material.id)
    db.session.commit()
    return ids


class TestGRNInventoryIntegration:
    def test_confirming_grn_with_material_item_updates_real_stock(self, app, db, client, seed_tenants, auth_headers):
        vendor_id, warehouse_id, material_id = _seed_vendor_warehouse_material(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["prc:write", "inv:read"])

        r = client.post("/v1/prc/purchase-orders", headers=headers, json={
            "vendor_id": str(vendor_id), "po_number": f"PO-{uuid.uuid4()}", "total_value": "500000",
            "lines": [{"description": "Test material", "quantity": "100", "unit_price": "5000", "material_item_id": str(material_id)}],
        })
        po_id = r.get_json()["id"]

        from app.modules.prc.models import PurchaseOrderLine
        _as_tenant(db, seed_tenants["a"])
        po_line = PurchaseOrderLine.query.filter_by(purchase_order_id=po_id).first()
        po_line_id = po_line.id

        r2 = client.post("/v1/prc/goods-receipt-notes", headers=headers, json={
            "purchase_order_id": po_id, "warehouse_id": str(warehouse_id),
            "lines": [{"po_line_id": str(po_line_id), "quantity_received": "100"}],
        })
        grn_id = r2.get_json()["id"]

        r3 = client.post(f"/v1/prc/goods-receipt-notes/{grn_id}/confirm", headers=headers, json={})
        assert r3.status_code == 200
        assert r3.get_json()["status"] == "confirmed"

        r4 = client.get(f"/v1/inv/warehouses/{warehouse_id}/stock", headers=headers)
        stock = r4.get_json()["data"]
        assert len(stock) == 1
        assert stock[0]["quantity_on_hand"] == "100.0000"
        assert stock[0]["average_unit_cost"] == "5000.0000"

    def test_confirming_without_warehouse_id_is_blocked_when_material_item_present(self, app, db, client, seed_tenants, auth_headers):
        vendor_id, warehouse_id, material_id = _seed_vendor_warehouse_material(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["prc:write"])

        r = client.post("/v1/prc/purchase-orders", headers=headers, json={
            "vendor_id": str(vendor_id), "po_number": f"PO-{uuid.uuid4()}", "total_value": "500000",
            "lines": [{"description": "Test material", "quantity": "100", "unit_price": "5000", "material_item_id": str(material_id)}],
        })
        po_id = r.get_json()["id"]

        from app.modules.prc.models import PurchaseOrderLine
        _as_tenant(db, seed_tenants["a"])
        po_line_id = PurchaseOrderLine.query.filter_by(purchase_order_id=po_id).first().id

        r2 = client.post("/v1/prc/goods-receipt-notes", headers=headers, json={
            "purchase_order_id": po_id,  # no warehouse_id
            "lines": [{"po_line_id": str(po_line_id), "quantity_received": "100"}],
        })
        grn_id = r2.get_json()["id"]

        r3 = client.post(f"/v1/prc/goods-receipt-notes/{grn_id}/confirm", headers=headers, json={})
        assert r3.status_code == 400

    def test_grn_without_any_material_item_lines_confirms_fine_without_warehouse(self, app, db, client, seed_tenants, auth_headers):
        """Backward compatible: a GRN for a service/labor PO line (no
        material_item_id at all) never needed a warehouse before this
        integration, and still doesn't."""
        vendor_id, warehouse_id, material_id = _seed_vendor_warehouse_material(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["prc:write"])

        r = client.post("/v1/prc/purchase-orders", headers=headers, json={
            "vendor_id": str(vendor_id), "po_number": f"PO-{uuid.uuid4()}", "total_value": "50000",
            "lines": [{"description": "Consulting services", "quantity": "1", "unit_price": "50000"}],  # no material_item_id
        })
        po_id = r.get_json()["id"]

        from app.modules.prc.models import PurchaseOrderLine
        _as_tenant(db, seed_tenants["a"])
        po_line_id = PurchaseOrderLine.query.filter_by(purchase_order_id=po_id).first().id

        r2 = client.post("/v1/prc/goods-receipt-notes", headers=headers, json={
            "purchase_order_id": po_id,
            "lines": [{"po_line_id": str(po_line_id), "quantity_received": "1"}],
        })
        grn_id = r2.get_json()["id"]

        r3 = client.post(f"/v1/prc/goods-receipt-notes/{grn_id}/confirm", headers=headers, json={})
        assert r3.status_code == 200
        assert r3.get_json()["status"] == "confirmed"

    def test_receiving_stock_twice_accumulates_correctly(self, app, db, client, seed_tenants, auth_headers):
        vendor_id, warehouse_id, material_id = _seed_vendor_warehouse_material(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["prc:write", "inv:read"])

        r = client.post("/v1/prc/purchase-orders", headers=headers, json={
            "vendor_id": str(vendor_id), "po_number": f"PO-{uuid.uuid4()}", "total_value": "1000000",
            "lines": [{"description": "Test material", "quantity": "200", "unit_price": "5000", "material_item_id": str(material_id)}],
        })
        po_id = r.get_json()["id"]

        from app.modules.prc.models import PurchaseOrderLine
        _as_tenant(db, seed_tenants["a"])
        po_line_id = PurchaseOrderLine.query.filter_by(purchase_order_id=po_id).first().id

        for qty in ("60", "40"):
            r2 = client.post("/v1/prc/goods-receipt-notes", headers=headers, json={
                "purchase_order_id": po_id, "warehouse_id": str(warehouse_id),
                "lines": [{"po_line_id": str(po_line_id), "quantity_received": qty}],
            })
            grn_id = r2.get_json()["id"]
            client.post(f"/v1/prc/goods-receipt-notes/{grn_id}/confirm", headers=headers, json={})

        r4 = client.get(f"/v1/inv/warehouses/{warehouse_id}/stock", headers=headers)
        assert r4.get_json()["data"][0]["quantity_on_hand"] == "100.0000"
