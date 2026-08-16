"""
Tests for app/commitments/ and its real integration into
app/modules/prc/services.py:submit_purchase_request.
"""
import uuid

from sqlalchemy import text


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def _seed_cbs_line(db, tenant_id, *, budgeted_amount=1000000):
    from app.modules.est.models import EstimateVersion, CostBreakdownStructure, CBSLineItem

    _as_tenant(db, tenant_id)
    ev = EstimateVersion(tenant_id=tenant_id, tender_id=uuid.uuid4(), version_number=1)
    db.session.add(ev)
    db.session.flush()

    cbs = CostBreakdownStructure(tenant_id=tenant_id, source_estimate_version_id=ev.id, is_approved=True)
    db.session.add(cbs)
    db.session.flush()

    cbs_line = CBSLineItem(tenant_id=tenant_id, cbs_id=cbs.id, description="Test budget line", budgeted_amount=budgeted_amount)
    db.session.add(cbs_line)
    db.session.flush()
    cbs_line_id = cbs_line.id
    db.session.commit()
    return cbs_line_id


def _seed_po(db, tenant_id, *, cbs_line_id, status, line_total):
    from app.modules.prc.models import Vendor, PurchaseOrder, PurchaseOrderLine

    _as_tenant(db, tenant_id)
    vendor = Vendor.query.filter_by(tenant_id=tenant_id).first()
    if not vendor:
        vendor = Vendor(tenant_id=tenant_id, name="Test Vendor")
        db.session.add(vendor)
        db.session.flush()

    po = PurchaseOrder(
        tenant_id=tenant_id, vendor_id=vendor.id, po_number=f"PO-TEST-{uuid.uuid4()}", status=status, total_value=line_total
    )
    db.session.add(po)
    db.session.flush()

    line = PurchaseOrderLine(
        tenant_id=tenant_id, purchase_order_id=po.id, cbs_line_item_id=cbs_line_id,
        description="Test line", quantity=1, unit_price=line_total, line_total=line_total,
    )
    db.session.add(line)
    db.session.commit()


class TestCommitmentSummary:
    def test_committed_amount_only_counts_approved_issued_closed_pos(self, app, db, seed_tenants):
        from app.commitments import services

        cbs_line_id = _seed_cbs_line(db, seed_tenants["a"], budgeted_amount=1000000)
        _seed_po(db, seed_tenants["a"], cbs_line_id=cbs_line_id, status="issued", line_total=300000)
        _seed_po(db, seed_tenants["a"], cbs_line_id=cbs_line_id, status="draft", line_total=200000)
        _seed_po(db, seed_tenants["a"], cbs_line_id=cbs_line_id, status="cancelled", line_total=500000)

        _as_tenant(db, seed_tenants["a"])
        summary = services.get_commitment_summary(seed_tenants["a"], cbs_line_id)

        assert summary["committed_amount"] == 300000
        assert summary["remaining_amount"] == 700000

    def test_multiple_committed_pos_sum_correctly(self, app, db, seed_tenants):
        from app.commitments import services

        cbs_line_id = _seed_cbs_line(db, seed_tenants["a"], budgeted_amount=1000000)
        _seed_po(db, seed_tenants["a"], cbs_line_id=cbs_line_id, status="approved", line_total=200000)
        _seed_po(db, seed_tenants["a"], cbs_line_id=cbs_line_id, status="issued", line_total=150000)
        _seed_po(db, seed_tenants["a"], cbs_line_id=cbs_line_id, status="closed", line_total=50000)

        _as_tenant(db, seed_tenants["a"])
        summary = services.get_commitment_summary(seed_tenants["a"], cbs_line_id)

        assert summary["committed_amount"] == 400000
        assert summary["remaining_amount"] == 600000

    def test_no_purchase_orders_means_fully_uncommitted(self, app, db, seed_tenants):
        from app.commitments import services

        cbs_line_id = _seed_cbs_line(db, seed_tenants["a"], budgeted_amount=1000000)

        _as_tenant(db, seed_tenants["a"])
        summary = services.get_commitment_summary(seed_tenants["a"], cbs_line_id)

        assert summary["committed_amount"] == 0
        assert summary["remaining_amount"] == 1000000

    def test_unknown_cbs_line_returns_none(self, app, db, seed_tenants):
        from app.commitments import services

        _as_tenant(db, seed_tenants["a"])
        summary = services.get_commitment_summary(seed_tenants["a"], uuid.uuid4())
        assert summary is None

    def test_cross_tenant_isolation(self, app, db, seed_tenants):
        from app.commitments import services

        cbs_line_id = _seed_cbs_line(db, seed_tenants["a"], budgeted_amount=1000000)
        _seed_po(db, seed_tenants["a"], cbs_line_id=cbs_line_id, status="issued", line_total=300000)

        # Tenant B must not be able to see tenant A's CBS line or its commitments.
        _as_tenant(db, seed_tenants["b"])
        summary = services.get_commitment_summary(seed_tenants["b"], cbs_line_id)
        assert summary is None

    def test_api_endpoint_returns_the_same_computation(self, app, db, client, seed_tenants, auth_headers):
        cbs_line_id = _seed_cbs_line(db, seed_tenants["a"], budgeted_amount=1000000)
        _seed_po(db, seed_tenants["a"], cbs_line_id=cbs_line_id, status="issued", line_total=300000)

        headers = auth_headers("a", permissions=["fin:read"])
        r = client.get(f"/v1/commitments/cbs-line-items/{cbs_line_id}/summary", headers=headers)

        assert r.status_code == 200
        assert r.get_json()["committed_amount"] == "300000.0000"
        assert r.get_json()["remaining_amount"] == "700000.0000"

    def test_api_endpoint_requires_fin_read_permission(self, app, db, client, seed_tenants, auth_headers):
        cbs_line_id = _seed_cbs_line(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["some:other_permission"])

        r = client.get(f"/v1/commitments/cbs-line-items/{cbs_line_id}/summary", headers=headers)
        assert r.status_code == 403


class TestPurchaseRequestBudgetIntegration:
    """The real integration: submit_purchase_request now computes a
    real remaining-budget figure when the caller doesn't supply one,
    instead of silently skipping the check entirely (the actual gap
    this module closes)."""

    def _seed_pr(self, db, tenant_id, *, cbs_line_id, estimated_total):
        from app.modules.prc.models import PurchaseRequest

        _as_tenant(db, tenant_id)
        pr = PurchaseRequest(
            tenant_id=tenant_id, cbs_line_item_id=cbs_line_id, description="Test PR",
            quantity=1, estimated_total=estimated_total, status="draft",
        )
        db.session.add(pr)
        db.session.flush()
        pr_id = pr.id
        db.session.commit()
        return pr_id

    def test_submit_is_blocked_when_computed_remaining_budget_is_breached(self, app, db, client, seed_tenants, auth_headers):
        cbs_line_id = _seed_cbs_line(db, seed_tenants["a"], budgeted_amount=1000000)
        _seed_po(db, seed_tenants["a"], cbs_line_id=cbs_line_id, status="issued", line_total=300000)  # remaining = 700,000
        pr_id = self._seed_pr(db, seed_tenants["a"], cbs_line_id=cbs_line_id, estimated_total=800000)  # breaches it

        headers = auth_headers("a", permissions=["prc:write"])
        r = client.post(f"/v1/prc/purchase-requests/{pr_id}/submit", headers=headers, json={})

        assert r.status_code == 409
        assert "700000" in r.get_json()["detail"]

    def test_submit_succeeds_when_within_computed_remaining_budget(self, app, db, client, seed_tenants, auth_headers):
        cbs_line_id = _seed_cbs_line(db, seed_tenants["a"], budgeted_amount=1000000)
        _seed_po(db, seed_tenants["a"], cbs_line_id=cbs_line_id, status="issued", line_total=300000)  # remaining = 700,000
        pr_id = self._seed_pr(db, seed_tenants["a"], cbs_line_id=cbs_line_id, estimated_total=100000)  # well within it

        headers = auth_headers("a", permissions=["prc:write"])
        r = client.post(f"/v1/prc/purchase-requests/{pr_id}/submit", headers=headers, json={})

        assert r.status_code == 200
        assert r.get_json()["status"] == "submitted"

    def test_pr_with_no_cbs_line_skips_the_check_as_before(self, app, db, client, seed_tenants, auth_headers):
        """A PR with no cbs_line_item_id has nothing to check against --
        must still submit successfully, matching pre-existing behavior
        for PRs that were never linked to a budget line."""
        from app.modules.prc.models import PurchaseRequest

        _as_tenant(db, seed_tenants["a"])
        pr = PurchaseRequest(tenant_id=seed_tenants["a"], description="No CBS line", quantity=1, estimated_total=9999999, status="draft")
        db.session.add(pr)
        db.session.flush()
        pr_id = pr.id
        db.session.commit()

        headers = auth_headers("a", permissions=["prc:write"])
        r = client.post(f"/v1/prc/purchase-requests/{pr_id}/submit", headers=headers, json={})

        assert r.status_code == 200

    def test_explicit_remaining_budget_still_overrides_the_computed_value(self, app, db, client, seed_tenants, auth_headers):
        """Backward compatible: a caller that already supplies its own
        remaining_budget is still honored as-is, not silently replaced
        by the computed figure."""
        cbs_line_id = _seed_cbs_line(db, seed_tenants["a"], budgeted_amount=1000000)
        _seed_po(db, seed_tenants["a"], cbs_line_id=cbs_line_id, status="issued", line_total=300000)  # computed remaining = 700,000
        pr_id = self._seed_pr(db, seed_tenants["a"], cbs_line_id=cbs_line_id, estimated_total=100000)

        headers = auth_headers("a", permissions=["prc:write"])
        # Explicitly supply a much lower remaining_budget than the real computed one -- should breach.
        r = client.post(f"/v1/prc/purchase-requests/{pr_id}/submit", headers=headers, json={"remaining_budget": "50000"})

        assert r.status_code == 409
        assert "50000" in r.get_json()["detail"]
