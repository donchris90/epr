"""Sales: cost of goods sold posted on delivery; customer payments against invoices."""
from decimal import Decimal

from sqlalchemy import text

from app.modules.fin.models import AccountsReceivableInvoice, GeneralLedgerLine, JournalEntry
from tests.test_sal_sales import _confirm, _deliver, _order, _post, _setup


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def _accounts(client, h, s, *, cogs=True, receipt=True):
    acc = lambda code, typ: _post(client, h, "/v1/fin/chart-of-accounts", code=code, name=code, account_type=typ).get_json()["id"]
    s.update(cogs=acc("5000", "expense"), inv=acc("1300", "asset"), bank=acc("1000", "asset"))
    r = client.put("/v1/sal/settings", headers=h, json=dict(
        company_id=s["company"], receivable_account_id=s["ar"], revenue_account_id=s["rev"], vat_account_id=s["vat"],
        vat_percent="7.5", payment_terms_days=14,
        **({"cogs_account_id": s["cogs"], "inventory_account_id": s["inv"]} if cogs else {}),
        **({"receipt_account_id": s["bank"]} if receipt else {})))
    assert r.status_code == 200, r.get_json()


def _invoiced(client, h, s, qty="10"):
    o = _order(client, h, s)
    _confirm(client, h, o["id"])
    _deliver(client, h, o, qty)
    inv = _post(client, h, f"/v1/sal/sales-orders/{o['id']}/invoice").get_json()
    return o, inv  # 10 x 500 = 5000 net, 375 VAT, 5375 gross


def _entries(db, tenant, source_reference=None, description_like=None):
    _as_tenant(db, tenant)
    q = JournalEntry.query.filter_by(source_module="SAL")
    if description_like:
        q = q.filter(JournalEntry.description.like(description_like))
    out = []
    for e in q.all():
        out.append((e, GeneralLedgerLine.query.filter_by(journal_entry_id=e.id).all()))
    return out


class TestCogs:
    def test_delivery_posts_cogs_against_inventory(self, app, db, client, seed_tenants, auth_headers, tenant_ids):
        h = auth_headers("a")
        s = _setup(client, h)
        _accounts(client, h, s)
        o = _order(client, h, s)
        _confirm(client, h, o["id"])
        assert _deliver(client, h, o, "4").status_code == 201  # 4 x 400 cost
        (entry, lines), = _entries(db, tenant_ids["a"], description_like="Cost of goods sold%")
        by = {str(l.account_id): l for l in lines}
        assert by[s["cogs"]].debit_amount == 1600 and by[s["inv"]].credit_amount == 1600

    def test_no_entry_when_cogs_accounts_are_not_set(self, app, db, client, seed_tenants, auth_headers, tenant_ids):
        h = auth_headers("a")
        s = _setup(client, h)
        _accounts(client, h, s, cogs=False)
        o = _order(client, h, s)
        _confirm(client, h, o["id"])
        assert _deliver(client, h, o, "4").status_code == 201
        assert _entries(db, tenant_ids["a"], description_like="Cost of goods sold%") == []

    def test_settings_need_both_cogs_accounts_or_neither(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h)
        acc = _post(client, h, "/v1/fin/chart-of-accounts", code="5000", name="COGS", account_type="expense").get_json()["id"]
        r = client.put("/v1/sal/settings", headers=h, json=dict(
            company_id=s["company"], receivable_account_id=s["ar"], revenue_account_id=s["rev"], vat_account_id=s["vat"], cogs_account_id=acc))
        assert r.status_code == 422

    def test_a_failed_cogs_posting_cancels_the_delivery(self, app, db, client, seed_tenants, auth_headers, tenant_ids):
        h = auth_headers("a")
        s = _setup(client, h)
        _accounts(client, h, s)
        o = _order(client, h, s)
        _confirm(client, h, o["id"])
        from app.modules.sal import services
        original = services.fin_services.post_journal_entry
        services.fin_services.post_journal_entry = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("ledger down"))
        try:
            try:
                _deliver(client, h, o, "4")
            except RuntimeError:
                pass
        finally:
            services.fin_services.post_journal_entry = original
        rows = client.get(f"/v1/inv/warehouses/{s['wh']}/stock", headers=h).get_json()["data"]
        assert Decimal(next(x for x in rows if x["material_item_id"] == s["bread"])["quantity_on_hand"]) == 100
        assert client.get(f"/v1/sal/sales-orders/{o['id']}", headers=h).get_json()["deliveries"] == []


class TestPayments:
    def _pay(self, client, h, inv, amount, **extra):
        return _post(client, h, f"/v1/sal/invoices/{inv['id']}/payments", amount=amount, **extra)

    def test_part_then_full_payment_posts_receipts_and_marks_paid(self, app, db, client, seed_tenants, auth_headers, tenant_ids):
        h = auth_headers("a")
        s = _setup(client, h)
        _accounts(client, h, s)
        o, inv = _invoiced(client, h, s)
        assert inv["payment_status"] == "unpaid" and Decimal(inv["balance"]) == Decimal("5375.00")
        r = self._pay(client, h, inv, "2000", method="transfer", reference="NIP-123")
        assert r.status_code == 201, r.get_json()
        listed = client.get("/v1/sal/invoices", headers=h).get_json()["data"][0]
        assert listed["payment_status"] == "partially_paid" and Decimal(listed["balance"]) == Decimal("3375.00")
        assert self._pay(client, h, inv, "3375.00").status_code == 201
        listed = client.get("/v1/sal/invoices", headers=h).get_json()["data"][0]
        assert listed["payment_status"] == "paid" and Decimal(listed["balance"]) == 0
        assert len(client.get(f"/v1/sal/invoices/{inv['id']}/payments", headers=h).get_json()["data"]) == 2

        entries = _entries(db, tenant_ids["a"], description_like="Payment received%")
        assert len(entries) == 2
        totals = {}
        for _, lines in entries:
            for l in lines:
                totals[str(l.account_id)] = totals.get(str(l.account_id), 0) + l.debit_amount - l.credit_amount
        assert totals[s["bank"]] == 5375 and totals[s["ar"]] == -5375
        _as_tenant(db, tenant_ids["a"])
        assert AccountsReceivableInvoice.query.filter_by(invoice_number=inv["number"]).one().status == "paid"

    def test_cannot_pay_more_than_is_owed_or_pay_a_paid_invoice(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h)
        _accounts(client, h, s)
        _, inv = _invoiced(client, h, s)
        assert self._pay(client, h, inv, "5375.01").status_code == 409
        assert self._pay(client, h, inv, "0").status_code == 422
        assert self._pay(client, h, inv, "-5").status_code == 422
        assert self._pay(client, h, inv, "5375.00").status_code == 201
        assert self._pay(client, h, inv, "1").status_code == 409
        paid = client.get("/v1/sal/invoices", headers=h).get_json()["data"][0]
        assert Decimal(paid["amount_paid"]) == Decimal("5375.00")

    def test_needs_a_deposit_account_and_a_known_method(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h)
        _accounts(client, h, s, receipt=False)
        _, inv = _invoiced(client, h, s)
        assert self._pay(client, h, inv, "100").status_code == 422  # no default receipt account
        assert self._pay(client, h, inv, "100", deposit_account_id=s["bank"]).status_code == 201
        assert self._pay(client, h, inv, "100", deposit_account_id=s["bank"], method="bitcoin").status_code == 422
        assert self._pay(client, h, inv, "100", deposit_account_id="00000000-0000-0000-0000-000000000000").status_code in (400, 404, 422)

    def test_failed_posting_leaves_the_invoice_unpaid(self, app, db, client, seed_tenants, auth_headers):
        h = auth_headers("a")
        s = _setup(client, h)
        _accounts(client, h, s)
        _, inv = _invoiced(client, h, s)
        bad = self._pay(client, h, inv, "100", deposit_account_id="00000000-0000-0000-0000-000000000000")
        assert bad.status_code >= 400
        listed = client.get("/v1/sal/invoices", headers=h).get_json()["data"][0]
        assert Decimal(listed["amount_paid"]) == 0 and listed["payment_status"] == "unpaid"
        assert client.get(f"/v1/sal/invoices/{inv['id']}/payments", headers=h).get_json()["data"] == []

    def test_a_failure_after_the_ledger_entry_leaves_no_orphan_entry(self, app, db, client, seed_tenants, auth_headers, tenant_ids):
        h = auth_headers("a")
        s = _setup(client, h)
        _accounts(client, h, s)
        _, inv = _invoiced(client, h, s)
        from app.modules.sal import services
        original = services.SalesPayment
        services.SalesPayment = lambda **k: (_ for _ in ()).throw(RuntimeError("db hiccup"))
        try:
            try:
                self._pay(client, h, inv, "100")
            except RuntimeError:
                pass
        finally:
            services.SalesPayment = original
        assert _entries(db, tenant_ids["a"], description_like="Payment received%") == []
        assert Decimal(client.get("/v1/sal/invoices", headers=h).get_json()["data"][0]["amount_paid"]) == 0

    def test_permissions_and_tenant_isolation(self, app, db, client, seed_tenants, auth_headers):
        a = auth_headers("a")
        s = _setup(client, a)
        _accounts(client, a, s)
        _, inv = _invoiced(client, a, s)
        assert self._pay(client, auth_headers("a", permissions=["sal:read", "sal:write"]), inv, "10").status_code == 403
        b = auth_headers("b")
        assert self._pay(client, b, inv, "10").status_code == 404
        assert client.get(f"/v1/sal/invoices/{inv['id']}/payments", headers=b).status_code == 404
