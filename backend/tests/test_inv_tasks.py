"""
Tests for app/modules/inv/tasks.py -- the first real Celery task in
this codebase, implementing the cross-module reorder -> draft
Purchase Request flow that app/modules/inv/services.py's own
check_reorder_levels docstring explicitly left for "the caller/a
Celery task" to do.

Calls the task directly as a plain function rather than through a
Celery worker/broker -- celery.Task's ContextTask override
(app/celery_app.py) already wraps every call in a real Flask app
context, so `task()` runs the real task body synchronously, no
running worker required. This is the same thing this task's own
manual verification during development did against the real dev
database.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import text

from app.modules.inv.tasks import check_and_create_reorder_purchase_requests


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def _seed_below_reorder(db, tenant_id, *, auto_create_pr=True, quantity_on_hand=10, reorder_point=50):
    from app.modules.inv.models import Warehouse, MaterialItem, StockItem, ReorderLevel

    _as_tenant(db, tenant_id)
    wh = Warehouse(tenant_id=tenant_id, name="Main Site Store", warehouse_type="site_store")
    db.session.add(wh)
    db.session.flush()

    item = MaterialItem(tenant_id=tenant_id, code="CEM-001", description="Portland Cement 50kg bags", unit="bags")
    db.session.add(item)
    db.session.flush()

    stock = StockItem(
        tenant_id=tenant_id, warehouse_id=wh.id, material_item_id=item.id,
        quantity_on_hand=quantity_on_hand, average_unit_cost=5000,
    )
    db.session.add(stock)

    level = ReorderLevel(
        tenant_id=tenant_id, warehouse_id=wh.id, material_item_id=item.id,
        reorder_point=reorder_point, reorder_quantity=200, auto_create_pr=auto_create_pr,
    )
    db.session.add(level)
    db.session.commit()
    return wh, item, level


class TestReorderAutoPR:
    def test_creates_draft_pr_when_stock_below_reorder_point(self, app, db, seed_tenants):
        tenant = seed_tenants["a"]
        _seed_below_reorder(db, tenant)

        result = check_and_create_reorder_purchase_requests()

        assert result["purchase_requests_created"] == 1
        assert result["errors"] == []

        _as_tenant(db, tenant)
        from app.modules.prc.models import PurchaseRequest
        prs = PurchaseRequest.query.filter_by(tenant_id=tenant).all()
        assert len(prs) == 1
        assert prs[0].status == "draft"  # never auto-submitted -- PRC-11 budget check still applies at submission
        assert prs[0].quantity == Decimal("200.0000")
        assert prs[0].unit == "bags"

    def test_does_not_create_pr_when_auto_create_pr_is_false(self, app, db, seed_tenants):
        tenant = seed_tenants["a"]
        _seed_below_reorder(db, tenant, auto_create_pr=False)

        result = check_and_create_reorder_purchase_requests()

        assert result["purchase_requests_created"] == 0

        _as_tenant(db, tenant)
        from app.modules.prc.models import PurchaseRequest
        assert PurchaseRequest.query.filter_by(tenant_id=tenant).count() == 0

    def test_does_not_create_pr_when_stock_is_above_reorder_point(self, app, db, seed_tenants):
        tenant = seed_tenants["a"]
        _seed_below_reorder(db, tenant, quantity_on_hand=100, reorder_point=50)

        result = check_and_create_reorder_purchase_requests()

        assert result["purchase_requests_created"] == 0

    def test_cooldown_prevents_duplicate_pr_on_immediate_rerun(self, app, db, seed_tenants):
        tenant = seed_tenants["a"]
        _seed_below_reorder(db, tenant)

        first = check_and_create_reorder_purchase_requests()
        second = check_and_create_reorder_purchase_requests()

        assert first["purchase_requests_created"] == 1
        assert second["purchase_requests_created"] == 0
        assert second["skipped_cooldown"] == 1

        _as_tenant(db, tenant)
        from app.modules.prc.models import PurchaseRequest
        assert PurchaseRequest.query.filter_by(tenant_id=tenant).count() == 1

    def test_creates_new_pr_after_cooldown_expires(self, app, db, seed_tenants):
        tenant = seed_tenants["a"]
        _, _, level = _seed_below_reorder(db, tenant)

        check_and_create_reorder_purchase_requests()

        # Simulate the cooldown having expired.
        _as_tenant(db, tenant)
        level.last_auto_pr_at = datetime.now(timezone.utc) - timedelta(days=8)
        db.session.commit()

        result = check_and_create_reorder_purchase_requests()

        assert result["purchase_requests_created"] == 1

        _as_tenant(db, tenant)
        from app.modules.prc.models import PurchaseRequest
        assert PurchaseRequest.query.filter_by(tenant_id=tenant).count() == 2

    def test_one_tenants_bad_data_does_not_abort_the_whole_run(self, app, db, seed_tenants, monkeypatch):
        """One tenant's failure partway through the loop (a query
        error, a data inconsistency, anything) must not prevent every
        other tenant's check from running in the same pass."""
        tenant_a, tenant_b = seed_tenants["a"], seed_tenants["b"]
        _seed_below_reorder(db, tenant_a)
        _seed_below_reorder(db, tenant_b)

        import app.modules.inv.tasks as tasks_module

        real_check = tasks_module.inv_services.check_reorder_levels

        def _raise_for_tenant_a(tenant_id, **kwargs):
            if str(tenant_id) == str(tenant_a):
                raise RuntimeError("simulated failure for tenant A")
            return real_check(tenant_id, **kwargs)

        monkeypatch.setattr(tasks_module.inv_services, "check_reorder_levels", _raise_for_tenant_a)

        result = check_and_create_reorder_purchase_requests()

        assert len(result["errors"]) == 1
        assert result["errors"][0]["tenant_id"] == str(tenant_a)
        # Tenant B's real PR still gets created despite tenant A's failure.
        assert result["purchase_requests_created"] == 1

        _as_tenant(db, tenant_b)
        from app.modules.prc.models import PurchaseRequest
        assert PurchaseRequest.query.filter_by(tenant_id=tenant_b).count() == 1
