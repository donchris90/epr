"""Sales: orders, partial deliveries, stock and cost, invoices posted to the ledger."""
from decimal import Decimal

from sqlalchemy import text

from app.modules.fin.models import GeneralLedgerLine, JournalEntry, AccountsReceivableInvoice


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def _post(client, h, url, **body):
    return client.post(url, headers=h, json=body)


def _setup(client, h, *, with_settings=True, stock="100", cost="400", vat_percent="7.5"):
    wh = _post(client, h, "/v1/inv/warehouses", name="Factory store", warehouse_type="central_yard").get_json()["id"]
    bread = _post(client, h, "/v1/inv/material-items", code="BREAD", description="Bread", unit="pc",
                  item_type="finished_good", sale_price="500").get_json()["id"]
    sugar = _post(client, h, "/v1/inv/material-items", code="SUGAR", description="Sugar", unit="kg").get_json()["id"]
    for item in (bread, sugar):
        assert _post(client, h, "/v1/inv/stock/receive", warehouse_id=wh, material_item_id=item, quantity=stock, unit_cost=cost).status_code == 201
    customer = _post(client, h, "/v1/bdc/clients", name="Shoprite").get_json()["id"]
    s = {"wh": wh, "bread": bread, "sugar": sugar, "client": customer}
    if with_settings:
        company = _post(client, h, "/v1/fin/companies", name="Co", is_default=True).get_json()["id"]
        acc = lambda code, typ: _post(client, h, "/v1/fin/chart-of-accounts", code=code, name=code, account_type=typ).get_json()["id"]
        s.update(company=company, ar=acc("1200", "asset"), rev=acc("4000", "revenue"), vat=acc("2200", "liability"))
        r = client.put("/v1/sal/settings", headers=h, json=dict(
            company_id=company, receivable_account_id=s["ar"], revenue_account_id=s["rev"], vat_account_id=s["vat"],
            vat_percent=vat_percent, payment_terms_days=14))
        assert r.status_code == 200, r.get_json()
    return s


def _order(client, h, s, lines=None, **extra):
    lines = lines or [{"material_item_id": s["bread"], "quantity": "10"}]
    r = _post(client, h, "/v1/sal/sales-orders", client_id=s["client"], warehouse_id=s["wh"], lines=lines, **extra)
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def _on_hand(client, h, wh, item):
    rows = client.get(f"/v1/inv/warehouses/{wh}/stock", headers=h).get_json()["data"]
    return Decimal(next(x for x in rows if x["material_item_id"] == item)["quantity_on_hand"])


def _confirm(client, h, oid):
    assert _post(client, h, f"/v1/sal/sales-orders/{oid}/confirm").status_code == 200


def _deliver(client, h, order, qty, **extra):
    return _post(client, h, f"/v1/sal/sales-orders/{order['id']}/deliveries",
                 lines=[{"order_line_id": order["lines"][0]["id"], "quantity": qty}], **extra)


class TestOrders:
    def test_defaults_price_from_item_and_totals_with_vat(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h)
        o = _order(client, h, s, [{"material_item_id": s["bread"], "quantity": "10"},
                                  {"material_item_id": s["sugar"], "quantity": "4", "unit_price": "1250.50"}])
        assert o["number"] == "SO-00001" and o["status"] == "draft"
        assert Decimal(o["lines"][0]["unit_price"]) == 500
        assert Decimal(o["subtotal"]) == Decimal("10002.00")  # 5000 + 5002
        assert Decimal(o["vat_percent"]) == Decimal("7.5") and Decimal(o["vat_amount"]) == Decimal("750.15")
        assert Decimal(o["total"]) == Decimal("10752.15")

    def test_missing_price_duplicates_and_unknowns_are_rejected(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h)
        base = dict(client_id=s["client"], warehouse_id=s["wh"])
        assert _post(client, h, "/v1/sal/sales-orders", **base, lines=[{"material_item_id": s["sugar"], "quantity": "1"}]).status_code == 422
        assert _post(client, h, "/v1/sal/sales-orders", **base, lines=[]).status_code == 422
        assert _post(client, h, "/v1/sal/sales-orders", **base, lines=[
            {"material_item_id": s["bread"], "quantity": "1"}, {"material_item_id": s["bread"], "quantity": "2"}]).status_code == 422
        assert _post(client, h, "/v1/sal/sales-orders", **base, lines=[{"material_item_id": s["bread"], "quantity": "0"}]).status_code == 422
        bad = dict(base, client_id="00000000-0000-0000-0000-000000000000")
        assert _post(client, h, "/v1/sal/sales-orders", **bad, lines=[{"material_item_id": s["bread"], "quantity": "1"}]).status_code == 404

    def test_only_a_draft_can_be_edited_and_the_vat_rate_is_snapshotted(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h)
        o = _order(client, h, s)
        client.put("/v1/sal/settings", headers=h, json=dict(
            company_id=s["company"], receivable_account_id=s["ar"], revenue_account_id=s["rev"], vat_account_id=s["vat"], vat_percent="0"))
        edit = client.put(f"/v1/sal/sales-orders/{o['id']}", headers=h, json=dict(
            client_id=s["client"], warehouse_id=s["wh"], lines=[{"material_item_id": s["bread"], "quantity": "20"}]))
        assert edit.status_code == 200 and Decimal(edit.get_json()["subtotal"]) == 10000
        assert Decimal(edit.get_json()["vat_percent"]) == Decimal("7.5")  # kept from when the order was made
        _confirm(client, h, o["id"])
        again = client.put(f"/v1/sal/sales-orders/{o['id']}", headers=h, json=dict(
            client_id=s["client"], warehouse_id=s["wh"], lines=[{"material_item_id": s["bread"], "quantity": "1"}]))
        assert again.status_code == 409


class TestDelivery:
    def test_must_be_confirmed_and_cannot_over_deliver(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h)
        o = _order(client, h, s)
        assert _deliver(client, h, o, "5").status_code == 409  # still a draft
        _confirm(client, h, o["id"])
        assert _deliver(client, h, o, "11").status_code == 409
        assert _deliver(client, h, o, "0").status_code == 422
        assert _on_hand(client, h, s["wh"], s["bread"]) == 100

    def test_partial_then_full_delivery_takes_stock_and_records_cost(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h)
        o = _order(client, h, s)
        _confirm(client, h, o["id"])
        d1 = _deliver(client, h, o, "4")
        assert d1.status_code == 201 and d1.get_json()["number"] == "DN-00001"
        assert Decimal(d1.get_json()["lines"][0]["valued_cost"]) == 1600  # 4 x 400
        got = client.get(f"/v1/sal/sales-orders/{o['id']}", headers=h).get_json()
        assert got["status"] == "partially_delivered" and Decimal(got["lines"][0]["delivered_quantity"]) == 4
        assert _on_hand(client, h, s["wh"], s["bread"]) == 96
        assert _deliver(client, h, o, "6").status_code == 201
        got = client.get(f"/v1/sal/sales-orders/{o['id']}", headers=h).get_json()
        assert got["status"] == "delivered"
        assert Decimal(got["delivered_value"]) == 5000 and Decimal(got["delivered_cost"]) == 4000
        assert Decimal(got["gross_margin"]) == 1000
        assert _on_hand(client, h, s["wh"], s["bread"]) == 90
        assert _deliver(client, h, o, "1").status_code == 409

    def test_a_short_item_rolls_the_whole_delivery_back(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h, stock="100")
        # sugar is drawn second and runs short; the bread already taken must come back
        low = _post(client, h, "/v1/inv/stock/issue", warehouse_id=s["wh"], material_item_id=s["sugar"], quantity="98")
        assert low.status_code == 200
        o = _order(client, h, s, [{"material_item_id": s["bread"], "quantity": "10"},
                                  {"material_item_id": s["sugar"], "quantity": "5", "unit_price": "100"}])
        _confirm(client, h, o["id"])
        r = _post(client, h, f"/v1/sal/sales-orders/{o['id']}/deliveries",
                  lines=[{"order_line_id": ln["id"], "quantity": ln["quantity"]} for ln in o["lines"]])
        assert r.status_code == 409
        assert _on_hand(client, h, s["wh"], s["bread"]) == 100
        got = client.get(f"/v1/sal/sales-orders/{o['id']}", headers=h).get_json()
        assert got["status"] == "confirmed" and got["deliveries"] == []

    def test_cancel_only_before_anything_is_delivered(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h)
        a, b = _order(client, h, s), _order(client, h, s)
        assert _post(client, h, f"/v1/sal/sales-orders/{a['id']}/cancel").get_json()["status"] == "cancelled"
        _confirm(client, h, b["id"])
        _deliver(client, h, b, "1")
        assert _post(client, h, f"/v1/sal/sales-orders/{b['id']}/cancel").status_code == 409
        assert _post(client, h, f"/v1/sal/sales-orders/{a['id']}/confirm").status_code == 409


class TestInvoicing:
    def _ledger(self, db, tenant, invoice_number):
        _as_tenant(db, tenant)
        ar = AccountsReceivableInvoice.query.filter_by(invoice_number=invoice_number).one()
        entry = JournalEntry.query.filter_by(id=ar.journal_entry_id).one()
        lines = GeneralLedgerLine.query.filter_by(journal_entry_id=entry.id).all()
        return ar, entry, lines

    def test_invoices_what_was_delivered_and_posts_balanced_entries_with_vat(self, app, db, client, seed_tenants, auth_headers, tenant_ids):
        h = auth_headers("a")
        s = _setup(client, h)
        o = _order(client, h, s)
        _confirm(client, h, o["id"])
        assert _post(client, h, f"/v1/sal/sales-orders/{o['id']}/invoice").status_code == 409  # nothing delivered yet
        _deliver(client, h, o, "4")
        r = _post(client, h, f"/v1/sal/sales-orders/{o['id']}/invoice")
        assert r.status_code == 201, r.get_json()
        inv = r.get_json()
        assert inv["number"] == "SI-00001"
        assert (Decimal(inv["net_amount"]), Decimal(inv["vat_amount"]), Decimal(inv["amount"])) == (2000, 150, 2150)
        ar, entry, lines = self._ledger(db, tenant_ids["a"], inv["number"])
        assert ar.amount == 2150 and ar.client_reference is not None and entry.source_module == "SAL"
        by = {str(l.account_id): l for l in lines}
        assert by[s["ar"]].debit_amount == 2150 and by[s["rev"]].credit_amount == 2000 and by[s["vat"]].credit_amount == 150
        assert sum(l.debit_amount for l in lines) == sum(l.credit_amount for l in lines)

    def test_never_invoices_the_same_delivery_twice(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h)
        o = _order(client, h, s)
        _confirm(client, h, o["id"])
        _deliver(client, h, o, "4")
        assert _post(client, h, f"/v1/sal/sales-orders/{o['id']}/invoice").status_code == 201
        assert _post(client, h, f"/v1/sal/sales-orders/{o['id']}/invoice").status_code == 409
        _deliver(client, h, o, "6")
        second = _post(client, h, f"/v1/sal/sales-orders/{o['id']}/invoice")
        assert second.status_code == 201
        assert Decimal(second.get_json()["net_amount"]) == 3000 and second.get_json()["number"] == "SI-00002"
        assert len(client.get("/v1/sal/invoices", headers=h).get_json()["data"]) == 2

    def test_zero_vat_posts_two_lines(self, app, db, client, seed_tenants, auth_headers, tenant_ids):
        h = auth_headers("a")
        s = _setup(client, h, vat_percent="0")
        o = _order(client, h, s)
        _confirm(client, h, o["id"])
        _deliver(client, h, o, "2")
        inv = _post(client, h, f"/v1/sal/sales-orders/{o['id']}/invoice").get_json()
        assert Decimal(inv["vat_amount"]) == 0 and Decimal(inv["amount"]) == 1000
        _, _, lines = self._ledger(db, tenant_ids["a"], inv["number"])
        assert len(lines) == 2

    def test_needs_sales_accounting_set_up(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h, with_settings=False)
        o = _order(client, h, s)
        _confirm(client, h, o["id"])
        _deliver(client, h, o, "2")
        r = _post(client, h, f"/v1/sal/sales-orders/{o['id']}/invoice")
        assert r.status_code == 409
        got = client.get(f"/v1/sal/sales-orders/{o['id']}", headers=h).get_json()
        assert Decimal(got["lines"][0]["invoiced_quantity"]) == 0  # the failed attempt left nothing behind

    def test_a_failure_part_way_through_invoicing_leaves_nothing_behind(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h)
        o = _order(client, h, s)  # snapshots 7.5% VAT
        _confirm(client, h, o["id"])
        _deliver(client, h, o, "4")
        # VAT later switched off with no VAT account: the old order still owes VAT, which can't be posted
        client.put("/v1/sal/settings", headers=h, json=dict(
            company_id=s["company"], receivable_account_id=s["ar"], revenue_account_id=s["rev"], vat_percent="0"))
        assert _post(client, h, f"/v1/sal/sales-orders/{o['id']}/invoice").status_code == 409
        got = client.get(f"/v1/sal/sales-orders/{o['id']}", headers=h).get_json()
        assert Decimal(got["lines"][0]["invoiced_quantity"]) == 0 and got["invoices"] == []
        assert client.get("/v1/sal/invoices", headers=h).get_json()["data"] == []

    def test_settings_require_a_vat_account_when_vat_applies(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h)
        r = client.put("/v1/sal/settings", headers=h, json=dict(
            company_id=s["company"], receivable_account_id=s["ar"], revenue_account_id=s["rev"], vat_percent="7.5"))
        assert r.status_code == 422


class TestAccess:
    def test_tenant_isolation_and_permissions(self, app, db, client, seed_tenants, auth_headers):
        a = auth_headers("a")
        s = _setup(client, a)
        o = _order(client, a, s)
        b = auth_headers("b")
        assert client.get(f"/v1/sal/sales-orders/{o['id']}", headers=b).status_code == 404
        assert client.get("/v1/sal/sales-orders", headers=b).get_json()["data"] == []
        reader = auth_headers("a", permissions=["sal:read"])
        assert client.get("/v1/sal/sales-orders", headers=reader).status_code == 200
        assert _post(client, reader, "/v1/sal/sales-orders", client_id=s["client"], warehouse_id=s["wh"],
                     lines=[{"material_item_id": s["bread"], "quantity": "1"}]).status_code == 403
        writer = auth_headers("a", permissions=["sal:read", "sal:write"])
        _confirm(client, writer, o["id"])
        _deliver(client, writer, o, "1")
        assert _post(client, writer, f"/v1/sal/sales-orders/{o['id']}/invoice").status_code == 403
        assert client.put("/v1/sal/settings", headers=writer, json={}).status_code == 403
