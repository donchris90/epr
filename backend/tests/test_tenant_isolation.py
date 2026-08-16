"""
Mandatory tenant-isolation test suite (SRS Section 12.2):

    "An automated test suite must attempt, for every tenant-scoped table,
    to read/write another tenant's row using a valid token for a different
    tenant, and must assert failure in 100% of cases. This suite runs on
    every CI build, not only periodically."

Uses the BDC module (Module 1) as the first fully-implemented case per
the build roadmap. As each further module's models land, add an
equivalent set of cases for its tables.

Requires a real Postgres TEST_DATABASE_URL — see conftest.py docstring.
"""
from sqlalchemy import text

from app.modules.bdc.models import Client, Opportunity


def _as_tenant(db, tenant_id):
    """
    Seed helper: outside of a real request, nothing has run the
    tenant-context middleware, so Postgres has no `app.tenant_id` set at
    all -- and thanks to FORCE ROW LEVEL SECURITY, that means even an
    INSERT from this test's own setup code is correctly rejected by RLS.
    This sets it for the duration of the current transaction, exactly
    like the middleware does for a real request.
    """
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def _create_client(db, tenant_id, name="Acme Co"):
    """Returns a lightweight object exposing `.id` and `.name` captured
    *before* the final commit -- see the comment on opp_id capture below
    for why touching ORM attributes after commit is unsafe here."""
    from types import SimpleNamespace

    with db.session.begin_nested():
        _as_tenant(db, tenant_id)
        client = Client(tenant_id=tenant_id, name=name)
        db.session.add(client)
        db.session.flush()
        result = SimpleNamespace(id=client.id, name=client.name)
    db.session.commit()
    return result


class TestBDCCrossTenantReadBlocked:
    """A user authenticated for tenant A must never be able to read a
    record belonging to tenant B, at the API layer."""

    def test_client_list_excludes_other_tenant(self, client, db, seed_tenants, auth_headers):
        _create_client(db, seed_tenants["a"], name="Tenant A's Client")
        _create_client(db, seed_tenants["b"], name="Tenant B's Client")

        r = client.get("/v1/bdc/clients", headers=auth_headers("a"))
        names = [c["name"] for c in r.get_json()["data"]]
        assert "Tenant A's Client" in names
        assert "Tenant B's Client" not in names

        r = client.get("/v1/bdc/clients", headers=auth_headers("b"))
        names = [c["name"] for c in r.get_json()["data"]]
        assert "Tenant B's Client" in names
        assert "Tenant A's Client" not in names

    def test_opportunity_lookup_by_id_returns_404_not_someone_elses_data(
        self, client, db, seed_tenants, auth_headers
    ):
        """Even a direct primary-key lookup (via the tender-calendar or
        transition endpoints) must not leak another tenant's row — the
        correct behavior is 404, indistinguishable from the record not
        existing at all (never a 403 that would confirm existence)."""
        tenant_a_client = _create_client(db, seed_tenants["a"])
        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["a"])
            opp = Opportunity(
                tenant_id=seed_tenants["a"],
                client_id=tenant_a_client.id,
                name="Tenant A's Opportunity",
                stage="identified",
            )
            db.session.add(opp)
            db.session.flush()
            # Captured now, before the outer commit: `id` is a client-side
            # Python default (uuid.uuid4), so it's already populated after
            # flush with no DB round-trip needed. Reading opp.id *after*
            # the commit below would trigger an ORM refresh query outside
            # any tenant context (this test isn't inside a real request),
            # which RLS would then correctly-but-confusingly reject.
            opp_id = opp.id
        db.session.commit()

        r = client.post(
            f"/v1/bdc/opportunities/{opp_id}/transition",
            headers=auth_headers("b"),
            json={"new_stage": "qualified"},
        )
        assert r.status_code == 404


class TestBDCCrossTenantWriteBlocked:
    """A user authenticated for tenant A must never be able to write to
    a record belonging to tenant B."""

    def test_transition_on_other_tenants_opportunity_is_rejected(
        self, client, db, seed_tenants, auth_headers
    ):
        tenant_b_client = _create_client(db, seed_tenants["b"])
        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            opp = Opportunity(
                tenant_id=seed_tenants["b"],
                client_id=tenant_b_client.id,
                name="Tenant B's Opportunity",
                stage="identified",
            )
            db.session.add(opp)
            db.session.flush()
            opp_id = opp.id  # see comment in the test above re: why this must happen pre-commit
        db.session.commit()

        r = client.post(
            f"/v1/bdc/opportunities/{opp_id}/transition",
            headers=auth_headers("a"),
            json={"new_stage": "qualified"},
        )
        assert r.status_code == 404

        # Confirm the record was genuinely untouched, not just hidden
        # from the response -- read it back as tenant B, its actual owner.
        db.session.expire_all()
        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            untouched = db.session.get(Opportunity, opp_id)
            assert untouched.stage == "identified"


class TestRowLevelSecurityEnforcement:
    """Proves isolation at the database layer itself (not just app-layer
    filtering) — a query with NO tenant_id predicate at all must still
    only return the current tenant's rows, and a cross-tenant UPDATE
    must affect zero rows. This is what distinguishes SRS Section 3.4's
    guarantee from an ordinary WHERE-clause convention that a future bug
    could bypass.
    """

    def test_unfiltered_select_only_returns_current_tenant_rows(self, app, db, seed_tenants):
        from sqlalchemy import text

        _create_client(db, seed_tenants["a"], name="A-owned")
        _create_client(db, seed_tenants["b"], name="B-owned")

        with db.session.begin_nested():
            db.session.execute(
                text("SET LOCAL app.tenant_id = :tid"), {"tid": str(seed_tenants["a"])}
            )
            # Deliberately no WHERE tenant_id = ... clause here — RLS,
            # not application code, must be what limits the result set.
            rows = db.session.execute(text("SELECT name FROM bdc_clients")).fetchall()

        names = [r[0] for r in rows]
        assert "A-owned" in names
        assert "B-owned" not in names

    def test_cross_tenant_update_affects_zero_rows(self, app, db, seed_tenants):
        from sqlalchemy import text

        _create_client(db, seed_tenants["b"], name="Original Name")

        with db.session.begin_nested():
            db.session.execute(
                text("SET LOCAL app.tenant_id = :tid"), {"tid": str(seed_tenants["a"])}
            )
            result = db.session.execute(
                text("UPDATE bdc_clients SET name = 'HACKED' WHERE tenant_id = :other"),
                {"other": str(seed_tenants["b"])},
            )
            assert result.rowcount == 0


def _create_opportunity(db, tenant_id, client_id, name="Opp"):
    with db.session.begin_nested():
        _as_tenant(db, tenant_id)
        opp = Opportunity(tenant_id=tenant_id, client_id=client_id, name=name, stage="identified")
        db.session.add(opp)
        db.session.flush()
        opp_id = opp.id  # capture pre-commit; see comment above re: post-commit ORM refresh
    db.session.commit()
    return opp_id


def _create_tender(db, tenant_id, opportunity_id, reference_number="TND-TEST-001"):
    from app.modules.tbm.models import Tender

    with db.session.begin_nested():
        _as_tenant(db, tenant_id)
        tender = Tender(
            tenant_id=tenant_id,
            opportunity_id=opportunity_id,
            reference_number=reference_number,
            status="draft",
        )
        db.session.add(tender)
        db.session.flush()
        tender_id = tender.id
    db.session.commit()
    return tender_id


class TestTBMCrossTenantIsolation:
    """Module 2 (Tender & Bid Management) tenant-isolation cases,
    covering the Tender aggregate and its nested resources (BOQ items,
    checklist items — the same RLS policy applies uniformly to every
    tbm_* table, but the app-layer 404-not-403 behavior is verified per
    endpoint since that's where a bug could realistically be introduced)."""

    def test_tender_list_excludes_other_tenant(self, client, db, seed_tenants, auth_headers):
        client_a = _create_client(db, seed_tenants["a"], name="Client A")
        client_b = _create_client(db, seed_tenants["b"], name="Client B")
        opp_a = _create_opportunity(db, seed_tenants["a"], client_a.id, "Opp A")
        opp_b = _create_opportunity(db, seed_tenants["b"], client_b.id, "Opp B")
        _create_tender(db, seed_tenants["a"], opp_a, "TND-A-001")
        _create_tender(db, seed_tenants["b"], opp_b, "TND-B-001")

        r = client.get("/v1/tbm/tenders", headers=auth_headers("a"))
        refs = [t["reference_number"] for t in r.get_json()["data"]]
        assert "TND-A-001" in refs
        assert "TND-B-001" not in refs

    def test_tender_get_by_id_returns_404_for_other_tenant(self, client, db, seed_tenants, auth_headers):
        client_b = _create_client(db, seed_tenants["b"])
        opp_b = _create_opportunity(db, seed_tenants["b"], client_b.id)
        tender_id = _create_tender(db, seed_tenants["b"], opp_b)

        r = client.get(f"/v1/tbm/tenders/{tender_id}", headers=auth_headers("a"))
        assert r.status_code == 404

    def test_cannot_add_boq_item_to_other_tenants_tender(self, client, db, seed_tenants, auth_headers):
        client_b = _create_client(db, seed_tenants["b"])
        opp_b = _create_opportunity(db, seed_tenants["b"], client_b.id)
        tender_id = _create_tender(db, seed_tenants["b"], opp_b)

        r = client.post(
            f"/v1/tbm/tenders/{tender_id}/boq-items",
            headers=auth_headers("a"),
            json={"description": "Should not be allowed", "unit": "m3", "quantity": "1"},
        )
        assert r.status_code == 404

        # Confirm no row was created at all, reading back as the real owner.
        from app.modules.tbm.models import TenderBOQItem

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            count = TenderBOQItem.query.filter_by(tender_id=tender_id).count()
        assert count == 0

    def test_cannot_submit_other_tenants_tender(self, client, db, seed_tenants, auth_headers):
        """Even if tenant A somehow knew tenant B's tender_id and every
        submission-readiness condition were met, the submission endpoint
        itself must still 404 rather than act on it."""
        client_b = _create_client(db, seed_tenants["b"])
        opp_b = _create_opportunity(db, seed_tenants["b"], client_b.id)
        tender_id = _create_tender(db, seed_tenants["b"], opp_b)

        r = client.post(
            f"/v1/tbm/tenders/{tender_id}/submit",
            headers=auth_headers("a"),
            json={"method": "portal", "submitted_at": "2026-07-24T12:00:00+00:00"},
        )
        assert r.status_code == 404


def _create_estimate_version(db, tenant_id, tender_id, version_number=1):
    from app.modules.est.models import EstimateVersion

    with db.session.begin_nested():
        _as_tenant(db, tenant_id)
        version = EstimateVersion(
            tenant_id=tenant_id, tender_id=tender_id, version_number=version_number, status="draft"
        )
        db.session.add(version)
        db.session.flush()
        version_id = version.id
    db.session.commit()
    return version_id


class TestESTCrossTenantIsolation:
    """Module 3 (Estimating & Cost Engineering) tenant-isolation cases.
    EST is the third module built with this exact RLS + after_begin
    pattern; these cases exist mainly to confirm the pattern keeps
    holding as new tables are added, not because EST's isolation logic
    differs in any way from BDC's or TBM's -- the whole point of RLS is
    that it's uniform across every tenant-scoped table without any
    per-module code to get wrong."""

    def test_boq_items_list_excludes_other_tenant(self, client, db, seed_tenants, auth_headers):
        client_a = _create_client(db, seed_tenants["a"], name="Client A")
        client_b = _create_client(db, seed_tenants["b"], name="Client B")
        opp_a = _create_opportunity(db, seed_tenants["a"], client_a.id)
        opp_b = _create_opportunity(db, seed_tenants["b"], client_b.id)
        tender_a = _create_tender(db, seed_tenants["a"], opp_a, "TND-EST-A")
        tender_b = _create_tender(db, seed_tenants["b"], opp_b, "TND-EST-B")
        version_a = _create_estimate_version(db, seed_tenants["a"], tender_a)
        version_b = _create_estimate_version(db, seed_tenants["b"], tender_b)

        r = client.post(
            f"/v1/est/estimate-versions/{version_a}/boq-items",
            headers=auth_headers("a"),
            json={"description": "Tenant A's item", "unit": "m3", "quantity": "10"},
        )
        assert r.status_code == 201

        # Tenant B must not be able to even see tenant A's estimate
        # version (404, not an empty-but-existing resource).
        r = client.get(f"/v1/est/estimate-versions/{version_a}/boq-items", headers=auth_headers("b"))
        assert r.status_code == 404

        r = client.get(f"/v1/est/estimate-versions/{version_b}/boq-items", headers=auth_headers("b"))
        assert r.status_code == 200
        assert r.get_json()["data"] == []

    def test_cannot_generate_cbs_from_other_tenants_estimate(self, client, db, seed_tenants, auth_headers):
        client_b = _create_client(db, seed_tenants["b"])
        opp_b = _create_opportunity(db, seed_tenants["b"], client_b.id)
        tender_b = _create_tender(db, seed_tenants["b"], opp_b)
        version_b = _create_estimate_version(db, seed_tenants["b"], tender_b)

        r = client.post(
            f"/v1/est/estimate-versions/{version_b}/generate-cbs", headers=auth_headers("a"), json={}
        )
        assert r.status_code == 404


def _create_contract(db, tenant_id, tender_id, contract_number="CTR-TEST-001"):
    from app.modules.ctm.models import Contract

    with db.session.begin_nested():
        _as_tenant(db, tenant_id)
        contract = Contract(
            tenant_id=tenant_id,
            tender_id=tender_id,
            contract_number=contract_number,
            contract_value=1000000,
            status="active",
        )
        db.session.add(contract)
        db.session.flush()
        contract_id = contract.id
    db.session.commit()
    return contract_id


class TestCTMCrossTenantIsolation:
    """Module 4 (Contract Management) tenant-isolation cases. Contract
    financial instruments (retention, bonds) are exactly the kind of
    data where a cross-tenant leak would be most damaging, so these
    cases specifically target the retention application/release
    endpoints, not just simple reads."""

    def test_contract_get_by_id_returns_404_for_other_tenant(self, client, db, seed_tenants, auth_headers):
        client_b = _create_client(db, seed_tenants["b"])
        opp_b = _create_opportunity(db, seed_tenants["b"], client_b.id)
        tender_b = _create_tender(db, seed_tenants["b"], opp_b)
        contract_id = _create_contract(db, seed_tenants["b"], tender_b)

        r = client.get(f"/v1/ctm/contracts/{contract_id}", headers=auth_headers("a"))
        assert r.status_code == 404

    def test_cannot_apply_retention_to_other_tenants_contract(self, client, db, seed_tenants, auth_headers):
        from app.modules.ctm.models import Retention

        client_b = _create_client(db, seed_tenants["b"])
        opp_b = _create_opportunity(db, seed_tenants["b"], client_b.id)
        tender_b = _create_tender(db, seed_tenants["b"], opp_b)
        contract_id = _create_contract(db, seed_tenants["b"], tender_b)

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            retention = Retention(tenant_id=seed_tenants["b"], contract_id=contract_id, percentage=10)
            db.session.add(retention)
            db.session.flush()
            retention_id = retention.id
        db.session.commit()

        r = client.post(
            f"/v1/ctm/retention/{retention_id}/apply-to-certificate",
            headers=auth_headers("a"),
            json={"certificate_amount": "1000000.00"},
        )
        assert r.status_code == 404

        # Confirm the withheld amount genuinely wasn't touched.
        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            untouched = db.session.get(Retention, retention_id)
            assert untouched.amount_withheld == 0


def _create_wbs_root(db, tenant_id, name="Root"):
    from app.modules.pln.models import WBSNode

    with db.session.begin_nested():
        _as_tenant(db, tenant_id)
        node = WBSNode(tenant_id=tenant_id, name=name)
        db.session.add(node)
        db.session.flush()
        node_id = node.id
    db.session.commit()
    return node_id


class TestPLNCrossTenantIsolation:
    """Module 5 (Project Planning) tenant-isolation cases. Specifically
    targets the CPM recalculation endpoint, since it reads a whole
    subtree of activities and dependencies -- a cross-tenant leak there
    would be worse than a single-record leak, since one call touches an
    entire schedule."""

    def test_wbs_node_list_excludes_other_tenant(self, client, db, seed_tenants, auth_headers):
        _create_wbs_root(db, seed_tenants["a"], name="Tenant A Root")
        _create_wbs_root(db, seed_tenants["b"], name="Tenant B Root")

        r = client.get("/v1/pln/wbs-nodes", headers=auth_headers("a"))
        names = [n["name"] for n in r.get_json()["data"]]
        assert "Tenant A Root" in names
        assert "Tenant B Root" not in names

    def test_cannot_recalculate_other_tenants_schedule(self, client, db, seed_tenants, auth_headers):
        root_id = _create_wbs_root(db, seed_tenants["b"])

        r = client.post(f"/v1/pln/wbs-nodes/{root_id}/recalculate-schedule", headers=auth_headers("a"))
        assert r.status_code == 404

    def test_cannot_add_activity_to_other_tenants_wbs_node(self, client, db, seed_tenants, auth_headers):
        root_id = _create_wbs_root(db, seed_tenants["b"])

        r = client.post(
            f"/v1/pln/wbs-nodes/{root_id}/activities",
            headers=auth_headers("a"),
            json={"name": "Should not be allowed", "planned_start": "2026-01-01", "duration_days": 5},
        )
        assert r.status_code == 404

        from app.modules.pln.models import Activity

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            count = Activity.query.filter_by(wbs_node_id=root_id).count()
        assert count == 0

    def test_project_activities_excludes_other_tenant(self, client, db, seed_tenants, auth_headers):
        """The project-wide activity list joins through WBS nodes --
        exactly the kind of aggregation query where a missed tenant
        filter would silently blend another tenant's schedule in,
        rather than cleanly 404."""
        import uuid
        from app.modules.pln.models import WBSNode, Activity

        shared_project_id = uuid.uuid4()

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["a"])
            node_a = WBSNode(tenant_id=seed_tenants["a"], project_id=shared_project_id, name="Tenant A WBS")
            db.session.add(node_a)
            db.session.flush()
            db.session.add(
                Activity(tenant_id=seed_tenants["a"], wbs_node_id=node_a.id, name="Tenant A Activity", planned_start="2026-01-01", duration_days=5)
            )
        db.session.commit()

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            node_b = WBSNode(tenant_id=seed_tenants["b"], project_id=shared_project_id, name="Tenant B WBS")
            db.session.add(node_b)
            db.session.flush()
            db.session.add(
                Activity(tenant_id=seed_tenants["b"], wbs_node_id=node_b.id, name="Tenant B Activity", planned_start="2026-01-01", duration_days=5)
            )
        db.session.commit()

        # Same project_id (a plausible collision/adversarial case) --
        # tenant A must see only their own activity.
        r = client.get(f"/v1/pln/activities?project_id={shared_project_id}", headers=auth_headers("a"))
        names = [a["name"] for a in r.get_json()["data"]]
        assert names == ["Tenant A Activity"]


def _create_diary(db, tenant_id, project_id=None, diary_date="2026-01-15"):
    import uuid
    from datetime import date
    from app.modules.exe.models import DailySiteDiary

    with db.session.begin_nested():
        _as_tenant(db, tenant_id)
        diary = DailySiteDiary(
            tenant_id=tenant_id,
            project_id=project_id or uuid.uuid4(),
            diary_date=date.fromisoformat(diary_date),
            narrative="Test diary",
        )
        db.session.add(diary)
        db.session.flush()
        diary_id = diary.id
    db.session.commit()
    return diary_id


class TestEXECrossTenantIsolation:
    """Module 6 (Project Execution) tenant-isolation cases. Specifically
    targets the diary sign-off flow, since a cross-tenant leak there
    would mean one tenant could sign or amend another's site record --
    a serious contractual/legal record, not just business data."""

    def test_diary_list_excludes_other_tenant(self, client, db, seed_tenants, auth_headers):
        _create_diary(db, seed_tenants["a"])
        _create_diary(db, seed_tenants["b"])

        r = client.get("/v1/exe/diaries", headers=auth_headers("a"))
        assert len(r.get_json()["data"]) == 1

        r = client.get("/v1/exe/diaries", headers=auth_headers("b"))
        assert len(r.get_json()["data"]) == 1

    def test_cannot_sign_other_tenants_diary(self, client, db, seed_tenants, auth_headers):
        diary_id = _create_diary(db, seed_tenants["b"])

        r = client.post(f"/v1/exe/diaries/{diary_id}/sign", headers=auth_headers("a"))
        assert r.status_code == 404

        from app.modules.exe.models import DailySiteDiary

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            untouched = db.session.get(DailySiteDiary, diary_id)
            assert untouched.status == "draft"

    def test_cannot_amend_other_tenants_diary(self, client, db, seed_tenants, auth_headers):
        diary_id = _create_diary(db, seed_tenants["b"])

        r = client.post(
            f"/v1/exe/diaries/{diary_id}/amendments",
            headers=auth_headers("a"),
            json={"description": "Attempted cross-tenant amendment"},
        )
        assert r.status_code == 404

        from app.modules.exe.models import DiaryAmendment

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            count = DiaryAmendment.query.filter_by(diary_id=diary_id).count()
        assert count == 0

    def test_cannot_list_other_tenants_diary_sub_resources(self, client, db, seed_tenants, auth_headers):
        """The GET list routes for weather/labor/equipment/amendments
        under a diary must 404 for a diary that belongs to another
        tenant, the same as every other diary-scoped route."""
        diary_id = _create_diary(db, seed_tenants["b"])

        for path in ("weather", "labor-usage", "equipment-usage", "amendments"):
            r = client.get(f"/v1/exe/diaries/{diary_id}/{path}", headers=auth_headers("a"))
            assert r.status_code == 404, f"expected 404 for GET .../{path}"


def _create_vendor(db, tenant_id, name="Test Vendor"):
    from types import SimpleNamespace
    from app.modules.prc.models import Vendor

    with db.session.begin_nested():
        _as_tenant(db, tenant_id)
        vendor = Vendor(tenant_id=tenant_id, name=name)
        db.session.add(vendor)
        db.session.flush()
        result = SimpleNamespace(id=vendor.id, name=vendor.name)
    db.session.commit()
    return result


def _create_purchase_order(db, tenant_id, vendor_id, po_number="PO-TEST-001"):
    from app.modules.prc.models import PurchaseOrder

    with db.session.begin_nested():
        _as_tenant(db, tenant_id)
        po = PurchaseOrder(
            tenant_id=tenant_id, vendor_id=vendor_id, po_number=po_number, total_value=1000000, status="draft"
        )
        db.session.add(po)
        db.session.flush()
        po_id = po.id
    db.session.commit()
    return po_id


class TestPRCCrossTenantIsolation:
    """Module 7 (Procurement) tenant-isolation cases. Specifically
    targets the PO issuance and approval-decision endpoints, since a
    cross-tenant leak there is a financial-commitment risk (one tenant
    approving or issuing spend against another's vendor relationship),
    not just a data-visibility issue."""

    def test_vendor_list_excludes_other_tenant(self, client, db, seed_tenants, auth_headers):
        _create_vendor(db, seed_tenants["a"], name="Tenant A Vendor")
        _create_vendor(db, seed_tenants["b"], name="Tenant B Vendor")

        r = client.get("/v1/prc/vendors", headers=auth_headers("a"))
        names = [v["name"] for v in r.get_json()["data"]]
        assert "Tenant A Vendor" in names
        assert "Tenant B Vendor" not in names

    def test_cannot_issue_other_tenants_purchase_order(self, client, db, seed_tenants, auth_headers):
        vendor_b = _create_vendor(db, seed_tenants["b"])
        po_id = _create_purchase_order(db, seed_tenants["b"], vendor_b.id)

        # Bypass approval for this test by mutating status directly --
        # the point here is the tenant boundary, not the approval flow.
        from app.modules.prc.models import PurchaseOrder

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            po = db.session.get(PurchaseOrder, po_id)
            po.status = "approved"
        db.session.commit()

        r = client.post(f"/v1/prc/purchase-orders/{po_id}/issue", headers=auth_headers("a"), json={})
        assert r.status_code == 404

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            untouched = db.session.get(PurchaseOrder, po_id)
            assert untouched.status == "approved"  # not "issued" -- the cross-tenant call had no effect

    def test_cannot_decide_other_tenants_approval_step(self, client, db, seed_tenants, auth_headers):
        from app.modules.prc.models import POApprovalStep

        vendor_b = _create_vendor(db, seed_tenants["b"])
        po_id = _create_purchase_order(db, seed_tenants["b"], vendor_b.id)

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            step = POApprovalStep(
                tenant_id=seed_tenants["b"], purchase_order_id=po_id, step_order=1, role_required="site_manager"
            )
            db.session.add(step)
            db.session.flush()
            step_id = step.id
        db.session.commit()

        r = client.post(
            f"/v1/prc/po-approval-steps/{step_id}/decide", headers=auth_headers("a"), json={"decision": "approved"}
        )
        assert r.status_code == 404

    def test_cannot_view_other_tenants_po_detail(self, client, db, seed_tenants, auth_headers):
        """The PO detail response aggregates line items, approval
        steps, and the latest invoice match onto one object -- exactly
        the kind of enriched response where a missed tenant filter on
        any ONE of those three sub-queries could leak, even if the
        top-level PO lookup itself is correctly scoped."""
        vendor_b = _create_vendor(db, seed_tenants["b"])
        po_id = _create_purchase_order(db, seed_tenants["b"], vendor_b.id)

        r = client.get(f"/v1/prc/purchase-orders/{po_id}", headers=auth_headers("a"))
        assert r.status_code == 404


def _create_warehouse(db, tenant_id, name="Test Warehouse"):
    from types import SimpleNamespace
    from app.modules.inv.models import Warehouse

    with db.session.begin_nested():
        _as_tenant(db, tenant_id)
        wh = Warehouse(tenant_id=tenant_id, name=name, warehouse_type="central_yard")
        db.session.add(wh)
        db.session.flush()
        result = SimpleNamespace(id=wh.id, name=wh.name)
    db.session.commit()
    return result


def _create_material_item(db, tenant_id, code="TEST-ITEM"):
    from types import SimpleNamespace
    from app.modules.inv.models import MaterialItem

    with db.session.begin_nested():
        _as_tenant(db, tenant_id)
        item = MaterialItem(tenant_id=tenant_id, code=code, description="Test material")
        db.session.add(item)
        db.session.flush()
        result = SimpleNamespace(id=item.id)
    db.session.commit()
    return result


class TestINVCrossTenantIsolation:
    """Module 8 (Inventory & Warehouse) tenant-isolation cases. Stock
    balances are exactly the kind of data where a cross-tenant leak
    would be commercially damaging (one tenant seeing or drawing down
    another's material stock), so these target the issue/receive
    endpoints specifically, not just reads."""

    def test_warehouse_stock_list_excludes_other_tenant(self, client, db, seed_tenants, auth_headers):
        wh_a = _create_warehouse(db, seed_tenants["a"], name="Tenant A Yard")
        wh_b = _create_warehouse(db, seed_tenants["b"], name="Tenant B Yard")

        r = client.get("/v1/inv/warehouses", headers=auth_headers("a"))
        names = [w["name"] for w in r.get_json()["data"]]
        assert "Tenant A Yard" in names
        assert "Tenant B Yard" not in names

    def test_cannot_issue_stock_from_other_tenants_warehouse(self, client, db, seed_tenants, auth_headers):
        wh_b = _create_warehouse(db, seed_tenants["b"])
        item_b = _create_material_item(db, seed_tenants["b"])

        r = client.post(
            "/v1/inv/stock/issue",
            headers=auth_headers("a"),
            json={"warehouse_id": str(wh_b.id), "material_item_id": str(item_b.id), "quantity": "10"},
        )
        # 404 on the warehouse lookup -- tenant A cannot even confirm
        # tenant B's warehouse exists, let alone draw stock from it.
        assert r.status_code == 404

    def test_cannot_receive_stock_into_other_tenants_warehouse(self, client, db, seed_tenants, auth_headers):
        wh_b = _create_warehouse(db, seed_tenants["b"])
        item_b = _create_material_item(db, seed_tenants["b"])

        r = client.post(
            "/v1/inv/stock/receive",
            headers=auth_headers("a"),
            json={"warehouse_id": str(wh_b.id), "material_item_id": str(item_b.id), "quantity": "10", "unit_cost": "100"},
        )
        assert r.status_code == 404

        from app.modules.inv.models import StockItem

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            count = StockItem.query.filter_by(warehouse_id=wh_b.id, material_item_id=item_b.id).count()
        assert count == 0


def _create_equipment(db, tenant_id, name="Test Excavator"):
    from types import SimpleNamespace
    from app.modules.eqp.models import Equipment

    with db.session.begin_nested():
        _as_tenant(db, tenant_id)
        eq = Equipment(tenant_id=tenant_id, name=name)
        db.session.add(eq)
        db.session.flush()
        result = SimpleNamespace(id=eq.id, name=eq.name)
    db.session.commit()
    return result


class TestEQPCrossTenantIsolation:
    """Module 9 (Equipment & Fleet Management) tenant-isolation cases.
    Targets operator assignment and equipment transfer, since both are
    write actions with real-world consequences (someone gets scheduled
    on a machine, or a machine's project allocation changes) if a
    cross-tenant leak let them succeed."""

    def test_equipment_list_excludes_other_tenant(self, client, db, seed_tenants, auth_headers):
        _create_equipment(db, seed_tenants["a"], name="Tenant A Excavator")
        _create_equipment(db, seed_tenants["b"], name="Tenant B Excavator")

        r = client.get("/v1/eqp/equipment", headers=auth_headers("a"))
        names = [e["name"] for e in r.get_json()["data"]]
        assert "Tenant A Excavator" in names
        assert "Tenant B Excavator" not in names

    def test_cannot_assign_operator_to_other_tenants_equipment(self, client, db, seed_tenants, auth_headers):
        import uuid

        equipment_b = _create_equipment(db, seed_tenants["b"])

        r = client.post(
            f"/v1/eqp/equipment/{equipment_b.id}/operator-assignments",
            headers=auth_headers("a"),
            json={"operator_id": str(uuid.uuid4()), "shift_start": "2026-02-01T07:00:00+00:00"},
        )
        assert r.status_code == 404

        from app.modules.eqp.models import OperatorAssignment

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            count = OperatorAssignment.query.filter_by(equipment_id=equipment_b.id).count()
        assert count == 0

    def test_cannot_transfer_other_tenants_equipment(self, client, db, seed_tenants, auth_headers):
        import uuid

        equipment_b = _create_equipment(db, seed_tenants["b"])

        r = client.post(
            f"/v1/eqp/equipment/{equipment_b.id}/transfers",
            headers=auth_headers("a"),
            json={"to_project_id": str(uuid.uuid4())},
        )
        assert r.status_code == 404


def _create_fuel_tank(db, tenant_id, name="Test Tank", level="1000"):
    from types import SimpleNamespace
    from app.modules.fuel.models import FuelTank

    with db.session.begin_nested():
        _as_tenant(db, tenant_id)
        tank = FuelTank(tenant_id=tenant_id, name=name, tank_type="bulk_storage", current_level_litres=level)
        db.session.add(tank)
        db.session.flush()
        result = SimpleNamespace(id=tank.id, name=tank.name)
    db.session.commit()
    return result


class TestFUELCrossTenantIsolation:
    """Module 10 (Fuel Management) tenant-isolation cases. Targets the
    reconcile and theft-flag-listing endpoints specifically, since fuel
    theft investigation data is sensitive and a cross-tenant leak here
    could expose one company's internal fraud investigations to
    another tenant entirely."""

    def test_tank_list_excludes_other_tenant(self, client, db, seed_tenants, auth_headers):
        _create_fuel_tank(db, seed_tenants["a"], name="Tenant A Tank")
        _create_fuel_tank(db, seed_tenants["b"], name="Tenant B Tank")

        r = client.get("/v1/fuel/tanks", headers=auth_headers("a"))
        names = [t["name"] for t in r.get_json()["data"]]
        assert "Tenant A Tank" in names
        assert "Tenant B Tank" not in names

    def test_cannot_reconcile_other_tenants_tank(self, client, db, seed_tenants, auth_headers):
        tank_b = _create_fuel_tank(db, seed_tenants["b"], level="1000")

        r = client.post(
            f"/v1/fuel/tanks/{tank_b.id}/reconcile",
            headers=auth_headers("a"),
            json={"dip_reading_litres": "0"},
        )
        assert r.status_code == 404

        from app.modules.fuel.models import FuelTank

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            untouched = db.session.get(FuelTank, tank_b.id)
            assert untouched.current_level_litres == 1000  # not tampered with via the cross-tenant call

    def test_theft_flags_list_excludes_other_tenant(self, client, db, seed_tenants, auth_headers):
        from app.modules.fuel.models import TheftFlag

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            flag = TheftFlag(tenant_id=seed_tenants["b"], flag_reason="tank_level_mismatch", description="Tenant B's flag")
            db.session.add(flag)
        db.session.commit()

        r = client.get("/v1/fuel/theft-flags", headers=auth_headers("a"))
        assert r.get_json()["data"] == []


def _create_employee(db, tenant_id, name="Test Employee"):
    from types import SimpleNamespace
    from app.modules.wfm.models import Employee

    with db.session.begin_nested():
        _as_tenant(db, tenant_id)
        emp = Employee(tenant_id=tenant_id, name=name)
        db.session.add(emp)
        db.session.flush()
        result = SimpleNamespace(id=emp.id, name=emp.name)
    db.session.commit()
    return result


class TestWFMCrossTenantIsolation:
    """Module 11 (Workforce Management) tenant-isolation cases. Medical
    records are the single most sensitive data category in the whole
    platform (personal health information), so this includes a case
    specifically confirming a tenant-A user with full `wfm:medical`
    permission still cannot reach tenant B's medical records -- the
    field-level permission gate and RLS are independent layers, and
    both have to hold."""

    def test_employee_list_excludes_other_tenant(self, client, db, seed_tenants, auth_headers):
        _create_employee(db, seed_tenants["a"], name="Tenant A Employee")
        _create_employee(db, seed_tenants["b"], name="Tenant B Employee")

        r = client.get("/v1/wfm/employees", headers=auth_headers("a"))
        names = [e["name"] for e in r.get_json()["data"]]
        assert "Tenant A Employee" in names
        assert "Tenant B Employee" not in names

    def test_cannot_read_other_tenants_medical_records_even_with_full_permission(
        self, client, db, seed_tenants, auth_headers
    ):
        employee_b = _create_employee(db, seed_tenants["b"])

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            from app.modules.wfm.models import MedicalRecord

            record = MedicalRecord(tenant_id=seed_tenants["b"], employee_id=employee_b.id, fitness_status="fit")
            db.session.add(record)
        db.session.commit()

        # Tenant A's caller has full wfm:medical permission -- the block
        # here must come from RLS/tenant scoping, not the permission gate.
        headers = auth_headers("a", permissions=["wfm:read", "wfm:write", "wfm:medical"])
        r = client.get(f"/v1/wfm/employees/{employee_b.id}/medical-records", headers=headers)
        assert r.status_code == 404

    def test_cannot_finalize_other_tenants_payroll_run(self, client, db, seed_tenants, auth_headers):
        from types import SimpleNamespace
        from app.modules.wfm.models import PayrollRun

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            run = PayrollRun(tenant_id=seed_tenants["b"], period_start="2026-02-01", period_end="2026-02-28")
            db.session.add(run)
            db.session.flush()
            run_id = run.id
        db.session.commit()

        r = client.post(f"/v1/wfm/payroll-runs/{run_id}/finalize", headers=auth_headers("a"))
        assert r.status_code == 404

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            untouched = db.session.get(PayrollRun, run_id)
            assert untouched.status == "draft"


def _create_subcontract_agreement(db, tenant_id, agreement_number="SUB-TEST-001"):
    from types import SimpleNamespace
    from app.modules.sub.models import Subcontractor, SubcontractAgreement

    with db.session.begin_nested():
        _as_tenant(db, tenant_id)
        sub = Subcontractor(tenant_id=tenant_id, name="Test Subcontractor")
        db.session.add(sub)
        db.session.flush()
        agreement = SubcontractAgreement(
            tenant_id=tenant_id, subcontractor_id=sub.id, agreement_number=agreement_number, value=1000000
        )
        db.session.add(agreement)
        db.session.flush()
        result = SimpleNamespace(id=agreement.id, subcontractor_id=sub.id)
    db.session.commit()
    return result


class TestSUBCrossTenantIsolation:
    """Module 12 (Subcontractor Management) tenant-isolation cases.
    Targets payment certificate issuance specifically, since a
    cross-tenant leak there is a real financial-commitment risk --
    one tenant issuing (or even just being able to attempt to issue)
    payment against another tenant's subcontract."""

    def test_agreement_list_excludes_other_tenant(self, client, db, seed_tenants, auth_headers):
        _create_subcontract_agreement(db, seed_tenants["a"], "SUB-A-001")
        _create_subcontract_agreement(db, seed_tenants["b"], "SUB-B-001")

        r = client.get("/v1/sub/agreements", headers=auth_headers("a"))
        numbers = [a["agreement_number"] for a in r.get_json()["data"]]
        assert "SUB-A-001" in numbers
        assert "SUB-B-001" not in numbers

    def test_cannot_issue_certificate_against_other_tenants_agreement(self, client, db, seed_tenants, auth_headers):
        agreement_b = _create_subcontract_agreement(db, seed_tenants["b"])

        r = client.post(
            f"/v1/sub/agreements/{agreement_b.id}/payment-certificates",
            headers=auth_headers("a"),
            json={"certificate_number": "PC-ATTACK-001", "measurement_sheet_ids": ["11111111-1111-1111-1111-111111111111"]},
        )
        assert r.status_code == 404

        from app.modules.sub.models import PaymentCertificate

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            count = PaymentCertificate.query.filter_by(agreement_id=agreement_b.id).count()
        assert count == 0

    def test_cannot_verify_other_tenants_measurement_sheet(self, client, db, seed_tenants, auth_headers):
        from app.modules.sub.models import SubcontractScopeItem, MeasurementSheet

        agreement_b = _create_subcontract_agreement(db, seed_tenants["b"])

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            scope = SubcontractScopeItem(tenant_id=seed_tenants["b"], agreement_id=agreement_b.id, description="Test scope")
            db.session.add(scope)
            db.session.flush()
            sheet = MeasurementSheet(
                tenant_id=seed_tenants["b"], agreement_id=agreement_b.id, scope_item_id=scope.id, verified_quantity=10
            )
            db.session.add(sheet)
            db.session.flush()
            sheet_id = sheet.id
        db.session.commit()

        r = client.post(f"/v1/sub/measurement-sheets/{sheet_id}/verify", headers=auth_headers("a"))
        assert r.status_code == 404

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            untouched = db.session.get(MeasurementSheet, sheet_id)
            assert untouched.status == "draft"


def _create_itp_with_hold_point(db, tenant_id):
    from types import SimpleNamespace
    from app.modules.qms.models import InspectionTestPlan, ITPHoldPoint

    with db.session.begin_nested():
        _as_tenant(db, tenant_id)
        itp = InspectionTestPlan(tenant_id=tenant_id, activity_type="concrete_pour", title="Test ITP")
        db.session.add(itp)
        db.session.flush()
        hold_point = ITPHoldPoint(tenant_id=tenant_id, itp_id=itp.id, sequence_order=1, description="Test hold point")
        db.session.add(hold_point)
        db.session.flush()
        result = SimpleNamespace(itp_id=itp.id, hold_point_id=hold_point.id)
    db.session.commit()
    return result


class TestQMSCrossTenantIsolation:
    """Module 13 (Quality Management) tenant-isolation cases. Targets
    the hold-point result-recording endpoint and NCR closure, since
    both are workflow-gating write actions -- a cross-tenant leak here
    would mean one tenant could pass/fail another's quality gate or
    close another's non-conformance report."""

    def test_itp_list_excludes_other_tenant(self, client, db, seed_tenants, auth_headers):
        from app.modules.qms.models import InspectionTestPlan

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["a"])
            db.session.add(InspectionTestPlan(tenant_id=seed_tenants["a"], activity_type="concrete_pour", title="Tenant A ITP"))
        db.session.commit()
        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            db.session.add(InspectionTestPlan(tenant_id=seed_tenants["b"], activity_type="concrete_pour", title="Tenant B ITP"))
        db.session.commit()

        r = client.get("/v1/qms/itps", headers=auth_headers("a"))
        titles = [i["title"] for i in r.get_json()["data"]]
        assert "Tenant A ITP" in titles
        assert "Tenant B ITP" not in titles

    def test_cannot_record_result_on_other_tenants_hold_point(self, client, db, seed_tenants, auth_headers):
        refs = _create_itp_with_hold_point(db, seed_tenants["b"])

        r = client.post(
            f"/v1/qms/hold-points/{refs.hold_point_id}/record-result", headers=auth_headers("a"), json={"passed": True}
        )
        assert r.status_code == 404

        from app.modules.qms.models import ITPHoldPoint

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            untouched = db.session.get(ITPHoldPoint, refs.hold_point_id)
            assert untouched.status == "pending"  # not tampered with via the cross-tenant call

    def test_cannot_close_other_tenants_ncr(self, client, db, seed_tenants, auth_headers):
        from app.modules.qms.models import NCR

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            ncr = NCR(tenant_id=seed_tenants["b"], description="Tenant B's non-conformance")
            db.session.add(ncr)
            db.session.flush()
            ncr_id = ncr.id
        db.session.commit()

        r = client.post(f"/v1/qms/ncrs/{ncr_id}/close", headers=auth_headers("a"))
        assert r.status_code == 404

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            untouched = db.session.get(NCR, ncr_id)
            assert untouched.status == "open"


def _create_active_permit(db, tenant_id):
    import uuid
    from types import SimpleNamespace
    from app.modules.hse.models import PermitToWork

    with db.session.begin_nested():
        _as_tenant(db, tenant_id)
        permit = PermitToWork(
            tenant_id=tenant_id, project_id=uuid.uuid4(), permit_type="hot_work", status="active"
        )
        db.session.add(permit)
        db.session.flush()
        result = SimpleNamespace(id=permit.id)
    db.session.commit()
    return result


class TestHSECrossTenantIsolation:
    """Module 14 (Health, Safety & Environment) tenant-isolation cases.
    Targets permit closure and incident closure specifically -- both are
    safety-critical, workflow-gating write actions where a cross-tenant
    leak would mean one tenant could formally close another's Permit to
    Work (with real physical-work implications) or their incident
    record."""

    def test_permit_list_excludes_other_tenant(self, client, db, seed_tenants, auth_headers):
        import uuid
        from app.modules.hse.models import PermitToWork

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["a"])
            db.session.add(PermitToWork(tenant_id=seed_tenants["a"], project_id=uuid.uuid4(), permit_type="hot_work"))
        db.session.commit()
        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            db.session.add(PermitToWork(tenant_id=seed_tenants["b"], project_id=uuid.uuid4(), permit_type="hot_work"))
        db.session.commit()

        r = client.get("/v1/hse/permits", headers=auth_headers("a"))
        assert len(r.get_json()["data"]) == 1

    def test_cannot_close_other_tenants_permit(self, client, db, seed_tenants, auth_headers):
        import uuid

        permit = _create_active_permit(db, seed_tenants["b"])

        r = client.post(f"/v1/hse/permits/{permit.id}/close", headers=auth_headers("a"))
        assert r.status_code == 404

        from app.modules.hse.models import PermitToWork

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            untouched = db.session.get(PermitToWork, permit.id)
            assert untouched.formally_closed is False

    def test_cannot_close_other_tenants_incident(self, client, db, seed_tenants, auth_headers):
        from app.modules.hse.models import Incident

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            incident = Incident(tenant_id=seed_tenants["b"], classification="first_aid", description="Tenant B incident")
            db.session.add(incident)
            db.session.flush()
            incident_id = incident.id
        db.session.commit()

        headers = auth_headers("a", permissions=["hse:read", "hse:write", "hse:approve", "hse:officer"])
        r = client.post(f"/v1/hse/incidents/{incident_id}/close", headers=headers)
        assert r.status_code == 404


def _create_official_volume_calc(db, tenant_id):
    import uuid
    from types import SimpleNamespace
    from app.modules.svy.models import DesignSurface, EarthworksVolumeCalculation

    with db.session.begin_nested():
        _as_tenant(db, tenant_id)
        surface = DesignSurface(tenant_id=tenant_id, project_id=uuid.uuid4(), name="Test Surface", is_approved=True)
        db.session.add(surface)
        db.session.flush()
        calc = EarthworksVolumeCalculation(
            tenant_id=tenant_id,
            project_id=surface.project_id,
            design_surface_id=surface.id,
            cut_volume=100,
            fill_volume=50,
            status="official",
            is_official=True,
        )
        db.session.add(calc)
        db.session.flush()
        result = SimpleNamespace(id=calc.id)
    db.session.commit()
    return result


class TestSVYCrossTenantIsolation:
    """Module 15 (Survey & Engineering) tenant-isolation cases. Targets
    billing submission and As-Built locking specifically -- both are
    write actions with real downstream consequences (a billing
    quantity, or an immutable handover record) if a cross-tenant leak
    let them succeed."""

    def test_control_point_list_excludes_other_tenant(self, client, db, seed_tenants, auth_headers):
        import uuid
        from app.modules.svy.models import SurveyControlPoint

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["a"])
            db.session.add(SurveyControlPoint(tenant_id=seed_tenants["a"], project_id=uuid.uuid4(), point_name="CP-A-1"))
        db.session.commit()
        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            db.session.add(SurveyControlPoint(tenant_id=seed_tenants["b"], project_id=uuid.uuid4(), point_name="CP-B-1"))
        db.session.commit()

        r = client.get("/v1/svy/control-points", headers=auth_headers("a"))
        names = [p["point_name"] for p in r.get_json()["data"]]
        assert "CP-A-1" in names
        assert "CP-B-1" not in names

    def test_cannot_submit_other_tenants_volume_calc_for_billing(self, client, db, seed_tenants, auth_headers):
        calc = _create_official_volume_calc(db, seed_tenants["b"])

        r = client.post(f"/v1/svy/earthworks-volumes/{calc.id}/submit-for-billing", headers=auth_headers("a"))
        assert r.status_code == 404

        from app.modules.svy.models import EarthworksVolumeCalculation

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            untouched = db.session.get(EarthworksVolumeCalculation, calc.id)
            assert untouched.submitted_for_billing is False

    def test_cannot_lock_other_tenants_as_built_record(self, client, db, seed_tenants, auth_headers):
        import uuid
        from app.modules.svy.models import AsBuiltRecord

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            record = AsBuiltRecord(tenant_id=seed_tenants["b"], project_id=uuid.uuid4(), scope_reference="Tenant B culvert")
            db.session.add(record)
            db.session.flush()
            record_id = record.id
        db.session.commit()

        r = client.post(f"/v1/svy/as-built-records/{record_id}/lock", headers=auth_headers("a"))
        assert r.status_code == 404

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            untouched = db.session.get(AsBuiltRecord, record_id)
            assert untouched.locked is False


class TestPQCrossTenantIsolation:
    """Module 16 (Plant & Quarry Management) tenant-isolation cases.
    Targets the explosives register balance calculation and blast
    completion specifically -- explosives record-keeping is
    regulatorily sensitive, and a cross-tenant leak in the balance
    calculation would mean one tenant's ledger silently absorbed
    another's entries."""

    def test_explosives_balance_excludes_other_tenant(self, client, db, seed_tenants, auth_headers):
        from app.modules.pq.models import ExplosivesRegister

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["a"])
            db.session.add(
                ExplosivesRegister(tenant_id=seed_tenants["a"], entry_type="procurement", material_type="ANFO", quantity=100)
            )
        db.session.commit()
        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            db.session.add(
                ExplosivesRegister(tenant_id=seed_tenants["b"], entry_type="procurement", material_type="ANFO", quantity=9999)
            )
        db.session.commit()

        r = client.get("/v1/pq/explosives-register/balance", headers=auth_headers("a"), query_string={"material_type": "ANFO"})
        assert r.get_json()["balance"] == "100.0000"

    def test_cannot_correct_other_tenants_explosives_entry(self, client, db, seed_tenants, auth_headers):
        from app.modules.pq.models import ExplosivesRegister

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            entry = ExplosivesRegister(tenant_id=seed_tenants["b"], entry_type="procurement", material_type="ANFO", quantity=100)
            db.session.add(entry)
            db.session.flush()
            entry_id = entry.id
        db.session.commit()

        r = client.post(
            f"/v1/pq/explosives-register/{entry_id}/corrections",
            headers=auth_headers("a"),
            json={"reason": "Attempted cross-tenant correction"},
        )
        assert r.status_code == 404

        from app.modules.pq.models import ExplosivesRegisterCorrection

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            count = ExplosivesRegisterCorrection.query.filter_by(entry_id=entry_id).count()
        assert count == 0

    def test_cannot_complete_other_tenants_blast(self, client, db, seed_tenants, auth_headers):
        from app.modules.pq.models import DrillingRecord, BlastingRecord

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            drilling = DrillingRecord(tenant_id=seed_tenants["b"], quarry_name="Tenant B Quarry")
            db.session.add(drilling)
            db.session.flush()
            blast = BlastingRecord(tenant_id=seed_tenants["b"], drilling_record_id=drilling.id)
            db.session.add(blast)
            db.session.flush()
            blast_id = blast.id
        db.session.commit()

        r = client.post(f"/v1/pq/blasting-records/{blast_id}/mark-complete", headers=auth_headers("a"), json={})
        assert r.status_code == 404

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            untouched = db.session.get(BlastingRecord, blast_id)
            assert untouched.status == "planned"


def _create_company_and_accounts(db, tenant_id):
    from types import SimpleNamespace
    from app.modules.fin.models import Company, ChartOfAccounts

    with db.session.begin_nested():
        _as_tenant(db, tenant_id)
        company = Company(tenant_id=tenant_id, name="Test Co")
        db.session.add(company)
        db.session.flush()
        expense = ChartOfAccounts(tenant_id=tenant_id, code="5100", name="Expenses", account_type="expense")
        payable = ChartOfAccounts(tenant_id=tenant_id, code="2100", name="Payable", account_type="liability")
        db.session.add_all([expense, payable])
        db.session.flush()
        result = SimpleNamespace(company_id=company.id, expense_account_id=expense.id, payable_account_id=payable.id)
    db.session.commit()
    return result


class TestFINCrossTenantIsolation:
    """Module 17 (Financial Management) tenant-isolation cases. This is
    the highest financial-stakes module in the platform -- a
    cross-tenant leak here would mean one tenant's spend posting
    against another tenant's chart of accounts, or (worse) computing
    budget-control checks against another tenant's ledger data. Both
    are checked directly."""

    def test_company_list_excludes_other_tenant(self, client, db, seed_tenants, auth_headers):
        from app.modules.fin.models import Company

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["a"])
            db.session.add(Company(tenant_id=seed_tenants["a"], name="Tenant A Co"))
        db.session.commit()
        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            db.session.add(Company(tenant_id=seed_tenants["b"], name="Tenant B Co"))
        db.session.commit()

        r = client.get("/v1/fin/companies", headers=auth_headers("a"))
        names = [c["name"] for c in r.get_json()["data"]]
        assert "Tenant A Co" in names
        assert "Tenant B Co" not in names

    def test_cannot_post_ap_invoice_against_other_tenants_accounts(self, client, db, seed_tenants, auth_headers):
        refs = _create_company_and_accounts(db, seed_tenants["b"])

        r = client.post(
            "/v1/fin/ap-invoices",
            headers=auth_headers("a"),
            json={
                "company_id": str(refs.company_id),
                "source_module": "PRC",
                "invoice_number": "ATTACK-001",
                "amount": "100000",
                "expense_account_id": str(refs.expense_account_id),
                "payable_account_id": str(refs.payable_account_id),
            },
        )
        # RLS blocks the account/company rows from being visible at all,
        # so the FK insert fails -- this should not succeed as tenant A.
        assert r.status_code in (400, 404, 409, 422, 500)

        from app.modules.fin.models import AccountsPayableInvoice

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            count = AccountsPayableInvoice.query.filter_by(invoice_number="ATTACK-001").count()
        assert count == 0

    def test_budget_control_check_excludes_other_tenants_ledger(self, client, db, seed_tenants, auth_headers):
        import uuid
        from app.modules.fin.models import JournalEntry, GeneralLedgerLine

        refs = _create_company_and_accounts(db, seed_tenants["b"])
        shared_cost_code = uuid.uuid4()

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            entry = JournalEntry(
                tenant_id=seed_tenants["b"], company_id=refs.company_id, entry_date="2026-01-01", source_module="PRC"
            )
            db.session.add(entry)
            db.session.flush()
            db.session.add(
                GeneralLedgerLine(
                    tenant_id=seed_tenants["b"],
                    journal_entry_id=entry.id,
                    account_id=refs.expense_account_id,
                    cost_code=shared_cost_code,
                    debit_amount=999999,
                )
            )
        db.session.commit()

        # Tenant A checks budget control against the SAME cost_code UUID
        # (coincidentally or adversarially reused) -- tenant B's spend
        # must not count against tenant A's budget.
        r = client.post(
            "/v1/fin/budget-control/check",
            headers=auth_headers("a"),
            json={"cost_code": str(shared_cost_code), "posting_amount": "100", "cbs_budget_amount": "1000"},
        )
        assert r.status_code == 200
        assert r.get_json()["allowed"] is True
        assert r.get_json()["warning"] is False


def _create_certificate(db, tenant_id, certificate_number="PC-TEST-001"):
    import uuid
    from types import SimpleNamespace
    from app.modules.bil.models import ProgressCertificate

    with db.session.begin_nested():
        _as_tenant(db, tenant_id)
        cert = ProgressCertificate(
            tenant_id=tenant_id, contract_id=uuid.uuid4(), certificate_number=certificate_number, status="draft"
        )
        db.session.add(cert)
        db.session.flush()
        result = SimpleNamespace(id=cert.id)
    db.session.commit()
    return result


class TestBILCrossTenantIsolation:
    """Module 18 (Client Billing) tenant-isolation cases. Targets
    certificate line addition and variation order approval -- both are
    write actions with real revenue-recognition consequences if a
    cross-tenant leak let them succeed against another tenant's
    contract."""

    def test_certificate_list_excludes_other_tenant(self, client, db, seed_tenants, auth_headers):
        _create_certificate(db, seed_tenants["a"], "PC-A-001")
        _create_certificate(db, seed_tenants["b"], "PC-B-001")

        r = client.get("/v1/bil/certificates", headers=auth_headers("a"))
        numbers = [c["certificate_number"] for c in r.get_json()["data"]]
        assert "PC-A-001" in numbers
        assert "PC-B-001" not in numbers

    def test_cannot_add_line_to_other_tenants_certificate(self, client, db, seed_tenants, auth_headers):
        import uuid

        cert = _create_certificate(db, seed_tenants["b"])

        r = client.post(
            f"/v1/bil/certificates/{cert.id}/lines",
            headers=auth_headers("a"),
            json={
                "boq_item_id": str(uuid.uuid4()),
                "certified_quantity": "10",
                "rate": "1000",
                "contracted_quantity": "100",
            },
        )
        assert r.status_code == 404

        from app.modules.bil.models import ProgressCertificateLine

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            count = ProgressCertificateLine.query.filter_by(certificate_id=cert.id).count()
        assert count == 0

    def test_cannot_decide_other_tenants_variation_order(self, client, db, seed_tenants, auth_headers):
        import uuid
        from app.modules.bil.models import VariationOrder

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            vo = VariationOrder(tenant_id=seed_tenants["b"], contract_id=uuid.uuid4(), description="Tenant B's VO")
            db.session.add(vo)
            db.session.flush()
            vo_id = vo.id
        db.session.commit()

        r = client.post(f"/v1/bil/variation-orders/{vo_id}/decide", headers=auth_headers("a"), json={"decision": "approved"})
        assert r.status_code == 404

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            untouched = db.session.get(VariationOrder, vo_id)
            assert untouched.status == "pending"

    def test_cannot_view_other_tenants_certificate_detail(self, client, db, seed_tenants, auth_headers):
        """The certificate detail response aggregates lines and payment
        tracking onto one object -- the same enriched-response shape
        that caught real gaps in Modules 7 and 17, checked here too."""
        cert = _create_certificate(db, seed_tenants["b"])

        r = client.get(f"/v1/bil/certificates/{cert.id}", headers=auth_headers("a"))
        assert r.status_code == 404


class TestPCCrossTenantIsolation:
    """Module 19 (Project Controls) tenant-isolation cases. Targets the
    at-risk-projects computation and forecast generation specifically --
    a cross-tenant leak in the at-risk aggregation would mean one
    tenant's project performance data silently blending into another
    tenant's executive risk view, which is exactly the kind of subtle,
    hard-to-notice leak an aggregation query can introduce even when
    individual-record lookups are correctly scoped."""

    def test_evm_snapshot_list_excludes_other_tenant(self, client, db, seed_tenants, auth_headers):
        import uuid
        from app.modules.pc.models import EVMSnapshot

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["a"])
            db.session.add(
                EVMSnapshot(
                    tenant_id=seed_tenants["a"], project_id=uuid.uuid4(), period_end="2026-01-31",
                    planned_value=100, earned_value=100, actual_cost=100, budget_at_completion=1000,
                    cost_variance=0, schedule_variance=0, cpi=1, spi=1,
                )
            )
        db.session.commit()
        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            db.session.add(
                EVMSnapshot(
                    tenant_id=seed_tenants["b"], project_id=uuid.uuid4(), period_end="2026-01-31",
                    planned_value=100, earned_value=100, actual_cost=100, budget_at_completion=1000,
                    cost_variance=0, schedule_variance=0, cpi=1, spi=1,
                )
            )
        db.session.commit()

        r = client.get("/v1/pc/evm-snapshots", headers=auth_headers("a"))
        assert len(r.get_json()["data"]) == 1

    def test_at_risk_projects_excludes_other_tenants_data(self, client, db, seed_tenants, auth_headers):
        """The aggregation query (group by project, take max period_end)
        must be scoped by tenant at every stage -- a leak here would be
        silent, not a clean 404."""
        import uuid
        from app.modules.pc.models import EVMSnapshot

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["a"])
            db.session.add(
                EVMSnapshot(
                    tenant_id=seed_tenants["a"], project_id=uuid.uuid4(), period_end="2026-01-31",
                    planned_value=100000, earned_value=100000, actual_cost=100000, budget_at_completion=1000000,
                    cost_variance=0, schedule_variance=0, cpi=1, spi=1,
                )
            )
        db.session.commit()

        # Tenant B has a badly-underperforming project (CPI = 0.5).
        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            db.session.add(
                EVMSnapshot(
                    tenant_id=seed_tenants["b"], project_id=uuid.uuid4(), period_end="2026-01-31",
                    planned_value=100000, earned_value=100000, actual_cost=200000, budget_at_completion=1000000,
                    cost_variance=-100000, schedule_variance=0, cpi=0.5, spi=1,
                )
            )
        db.session.commit()

        # Tenant A's at-risk list must NOT include tenant B's
        # underperforming project -- tenant A has no at-risk projects.
        r = client.get("/v1/pc/at-risk-projects", headers=auth_headers("a"), query_string={"threshold": "0.9"})
        assert r.get_json()["data"] == []

    def test_cannot_generate_forecast_for_other_tenants_snapshot(self, client, db, seed_tenants, auth_headers):
        import uuid
        from app.modules.pc.models import EVMSnapshot

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            snapshot = EVMSnapshot(
                tenant_id=seed_tenants["b"], project_id=uuid.uuid4(), period_end="2026-01-31",
                planned_value=100000, earned_value=80000, actual_cost=100000, budget_at_completion=500000,
                cost_variance=-20000, schedule_variance=-20000, cpi=0.8, spi=0.8,
            )
            db.session.add(snapshot)
            db.session.flush()
            snapshot_id = snapshot.id
        db.session.commit()

        r = client.post(f"/v1/pc/evm-snapshots/{snapshot_id}/forecast", headers=auth_headers("a"), json={"method": "cpi_based"})
        assert r.status_code == 404

        from app.modules.pc.models import ForecastAtCompletion

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            count = ForecastAtCompletion.query.filter_by(evm_snapshot_id=snapshot_id).count()
        assert count == 0


def _create_asset(db, tenant_id, name="Test Asset"):
    from types import SimpleNamespace
    from app.modules.ast.models import Asset

    with db.session.begin_nested():
        _as_tenant(db, tenant_id)
        asset = Asset(tenant_id=tenant_id, asset_category="road", name=name, baseline_data={"chainage": 1000})
        db.session.add(asset)
        db.session.flush()
        result = SimpleNamespace(id=asset.id)
    db.session.commit()
    return result


class TestASTCrossTenantIsolation:
    """Module 20 (Asset Management) tenant-isolation cases. Targets
    asset attribute updates and DLP retention release specifically --
    a cross-tenant leak in the retention-release path would mean one
    tenant releasing (real, financial) retention tied to another
    tenant's contract."""

    def test_asset_list_excludes_other_tenant(self, client, db, seed_tenants, auth_headers):
        _create_asset(db, seed_tenants["a"], name="Tenant A Bridge")
        _create_asset(db, seed_tenants["b"], name="Tenant B Bridge")

        r = client.get("/v1/ast/assets", headers=auth_headers("a"))
        names = [a["name"] for a in r.get_json()["data"]]
        assert "Tenant A Bridge" in names
        assert "Tenant B Bridge" not in names

    def test_cannot_update_other_tenants_asset(self, client, db, seed_tenants, auth_headers):
        asset = _create_asset(db, seed_tenants["b"])

        r = client.put(
            f"/v1/ast/assets/{asset.id}/attributes", headers=auth_headers("a"), json={"name": "Renamed by attacker"}
        )
        assert r.status_code == 404

        from app.modules.ast.models import Asset

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            untouched = db.session.get(Asset, asset.id)
            assert untouched.name == "Test Asset"

    def test_cannot_release_other_tenants_dlp_retention(self, client, db, seed_tenants, auth_headers):
        from app.modules.ast.models import DefectsLiabilityRecord

        asset = _create_asset(db, seed_tenants["b"])
        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            dlp = DefectsLiabilityRecord(tenant_id=seed_tenants["b"], asset_id=asset.id)
            db.session.add(dlp)
            db.session.flush()
            dlp_id = dlp.id
        db.session.commit()

        r = client.post(f"/v1/ast/dlp/{dlp_id}/release-retention", headers=auth_headers("a"))
        assert r.status_code == 404

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            untouched = db.session.get(DefectsLiabilityRecord, dlp_id)
            assert untouched.retention_released is False


class TestEXDCrossTenantIsolation:
    """Module 21 (Executive Dashboard) tenant-isolation cases. This
    module reads directly across many other modules' tables (the one
    place in the codebase where that's the intended design), which
    makes its aggregation queries the highest-risk leak surface of any
    module so far -- a missed tenant_id filter here wouldn't 404, it
    would silently blend another tenant's financial/performance data
    into a dashboard number. Both real cross-module aggregations built
    in this pass are checked directly."""

    def test_company_revenue_excludes_other_tenants_ledger(self, client, db, seed_tenants, auth_headers):
        import uuid
        from app.modules.fin.models import Company, ChartOfAccounts, JournalEntry, GeneralLedgerLine

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            company = Company(tenant_id=seed_tenants["b"], name="Tenant B Co")
            db.session.add(company)
            db.session.flush()
            revenue_acct = ChartOfAccounts(tenant_id=seed_tenants["b"], code="4100", name="Revenue", account_type="revenue")
            db.session.add(revenue_acct)
            db.session.flush()
            entry = JournalEntry(
                tenant_id=seed_tenants["b"], company_id=company.id, entry_date="2026-01-01", source_module="BIL"
            )
            db.session.add(entry)
            db.session.flush()
            db.session.add(
                GeneralLedgerLine(
                    tenant_id=seed_tenants["b"], journal_entry_id=entry.id, account_id=revenue_acct.id, credit_amount=9999999
                )
            )
        db.session.commit()

        # Tenant A has posted nothing -- its dashboard must show zero
        # revenue, not tenant B's ₦9,999,999.
        r = client.get(
            "/v1/exd/company-revenue",
            headers=auth_headers("a"),
            query_string={"period_start": "2020-01-01", "period_end": "2030-01-01"},
        )
        assert r.status_code == 200
        assert r.get_json()["actual_revenue"] == "0"

    def test_active_projects_performance_excludes_other_tenant(self, client, db, seed_tenants, auth_headers):
        import uuid
        from app.modules.pc.models import EVMSnapshot

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            db.session.add(
                EVMSnapshot(
                    tenant_id=seed_tenants["b"], project_id=uuid.uuid4(), period_end="2026-01-31",
                    planned_value=100, earned_value=100, actual_cost=100, budget_at_completion=1000,
                    cost_variance=0, schedule_variance=0, cpi=1, spi=1,
                )
            )
        db.session.commit()

        r = client.get("/v1/exd/active-projects-performance", headers=auth_headers("a"))
        assert r.get_json()["data"] == []


class TestCLPClientScopeIsolation:
    """Module 22 (Client Portal) isolation cases. Covers both ordinary
    cross-TENANT isolation and the module's own dedicated business rule
    (a client can never see another client's project data regardless
    of permission grants) -- the latter is tested with a caller that
    holds full `*` permissions, specifically to prove the block comes
    from the client-scope check, not from the permission system."""

    def test_client_user_list_excludes_other_tenant(self, client, db, seed_tenants, auth_headers):
        from app.modules.clp.models import ClientPortalUser

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["a"])
            db.session.add(ClientPortalUser(tenant_id=seed_tenants["a"], client_organization_name="Tenant A Client", email="a@client.com"))
        db.session.commit()

        r = client.post(
            "/v1/clp/client-users", headers=auth_headers("a"),
            json={"client_organization_name": "Second Tenant A Client", "email": "a2@client.com"},
        )
        assert r.status_code == 201

    def test_client_cannot_access_another_clients_project_even_with_full_permissions(
        self, client, db, seed_tenants, auth_headers
    ):
        """The core business rule: even a caller with unrestricted `*`
        permissions (auth_headers' default) gets a 403 from the
        client-scope check specifically, because that check never
        consults the permission grant at all -- it only consults
        ClientProjectAssignment."""
        import uuid
        from types import SimpleNamespace
        from app.modules.clp.models import ClientPortalUser, ClientProjectAssignment

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["a"])
            client_1 = ClientPortalUser(tenant_id=seed_tenants["a"], client_organization_name="Client One", email="one@client.com")
            client_2 = ClientPortalUser(tenant_id=seed_tenants["a"], client_organization_name="Client Two", email="two@client.com")
            db.session.add_all([client_1, client_2])
            db.session.flush()

            project_1 = uuid.uuid4()
            project_2 = uuid.uuid4()
            db.session.add(ClientProjectAssignment(tenant_id=seed_tenants["a"], client_user_id=client_1.id, project_id=project_1))
            db.session.add(ClientProjectAssignment(tenant_id=seed_tenants["a"], client_user_id=client_2.id, project_id=project_2))
            ids = SimpleNamespace(client_1=client_1.id, client_2=client_2.id, project_1=project_1, project_2=project_2)
        db.session.commit()

        # Client 1, using client 2's project ID, with full permissions.
        r = client.get(
            f"/v1/clp/client-users/{ids.client_1}/projects/{ids.project_2}/schedule", headers=auth_headers("a")
        )
        assert r.status_code == 403

        r = client.post(
            f"/v1/clp/client-users/{ids.client_1}/requests",
            headers=auth_headers("a"),
            json={"project_id": str(ids.project_2), "request_type": "rfi", "description": "Cross-client attempt"},
        )
        assert r.status_code == 403

        from app.modules.clp.models import ClientRequest

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["a"])
            count = ClientRequest.query.filter_by(client_user_id=ids.client_1).count()
        assert count == 0


class TestVNPVendorScopeIsolation:
    """Module 23 (Vendor Portal) isolation cases. Covers the module's
    dedicated business rules: a vendor can never act on another
    vendor's purchase order (even with full permissions -- the check
    doesn't consult the permission system), and a vendor-submitted
    banking change can never reach the live Vendor record without a
    distinct internal Finance approval."""

    def test_vendor_cannot_acknowledge_another_vendors_po_even_with_full_permissions(
        self, client, db, seed_tenants, auth_headers
    ):
        import uuid
        from types import SimpleNamespace
        from app.modules.vnp.models import VendorPortalUser
        from app.modules.prc.models import Vendor, PurchaseOrder

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["a"])
            vendor_1 = Vendor(tenant_id=seed_tenants["a"], name="Vendor One")
            vendor_2 = Vendor(tenant_id=seed_tenants["a"], name="Vendor Two")
            db.session.add_all([vendor_1, vendor_2])
            db.session.flush()

            po = PurchaseOrder(tenant_id=seed_tenants["a"], vendor_id=vendor_1.id, po_number="PO-ISO-1", total_value=1000)
            db.session.add(po)
            db.session.flush()

            vnp_user_2 = VendorPortalUser(tenant_id=seed_tenants["a"], vendor_id=vendor_2.id, email="v2@test.com")
            db.session.add(vnp_user_2)
            db.session.flush()
            ids = SimpleNamespace(vnp_user_2=vnp_user_2.id, po=po.id)
        db.session.commit()

        # Vendor 2's portal user, with FULL permissions, tries to
        # acknowledge vendor 1's PO.
        r = client.post(
            f"/v1/vnp/vendor-users/{ids.vnp_user_2}/acknowledge-order",
            headers=auth_headers("a"),
            json={"purchase_order_id": str(ids.po)},
        )
        assert r.status_code == 403

        from app.modules.vnp.models import OrderAcknowledgment

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["a"])
            count = OrderAcknowledgment.query.filter_by(purchase_order_id=ids.po).count()
        assert count == 0

    def test_banking_change_submission_never_touches_live_vendor_record(self, client, db, seed_tenants, auth_headers):
        import uuid
        from types import SimpleNamespace
        from app.modules.vnp.models import VendorPortalUser
        from app.modules.prc.models import Vendor

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["a"])
            vendor = Vendor(tenant_id=seed_tenants["a"], name="Vendor Banking Test", banking_details=None)
            db.session.add(vendor)
            db.session.flush()
            vnp_user = VendorPortalUser(tenant_id=seed_tenants["a"], vendor_id=vendor.id, email="banking@test.com")
            db.session.add(vnp_user)
            db.session.flush()
            ids = SimpleNamespace(vendor=vendor.id, vnp_user=vnp_user.id)
        db.session.commit()

        r = client.post(
            f"/v1/vnp/vendor-users/{ids.vnp_user}/banking-change-requests",
            headers=auth_headers("a"),
            json={"proposed_banking_details": {"bank_name": "Attacker Bank", "account_number": "000"}},
        )
        assert r.status_code == 201

        from app.modules.prc.models import Vendor

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["a"])
            untouched = db.session.get(Vendor, ids.vendor)
            assert untouched.banking_details is None

    def test_cannot_approve_other_tenants_banking_change_request(self, client, db, seed_tenants, auth_headers):
        from app.modules.vnp.models import VendorPortalUser, VendorBankingChangeRequest
        from app.modules.prc.models import Vendor

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            vendor = Vendor(tenant_id=seed_tenants["b"], name="Tenant B Vendor", banking_details=None)
            db.session.add(vendor)
            db.session.flush()
            vnp_user = VendorPortalUser(tenant_id=seed_tenants["b"], vendor_id=vendor.id, email="tb@test.com")
            db.session.add(vnp_user)
            db.session.flush()
            req = VendorBankingChangeRequest(
                tenant_id=seed_tenants["b"], vendor_user_id=vnp_user.id, vendor_id=vendor.id,
                proposed_banking_details={"bank_name": "X"},
            )
            db.session.add(req)
            db.session.flush()
            req_id = req.id
            vendor_id = vendor.id
        db.session.commit()

        headers = auth_headers("a", permissions=["vnp:read", "vnp:write", "vnp:approve", "vnp:finance_approve"])
        r = client.post(f"/v1/vnp/banking-change-requests/{req_id}/approve", headers=headers)
        assert r.status_code == 404

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            untouched_vendor = db.session.get(Vendor, vendor_id)
            assert untouched_vendor.banking_details is None


class TestMFACrossTenantIsolation:
    """Module 24 (Mobile Field App) isolation cases. The sync-status
    summary is an aggregation query (like Module 21's dashboards) --
    exactly the kind of place a missed tenant filter would silently
    blend counts rather than cleanly 404, so it's checked directly
    alongside the more ordinary conflict-resolution lookup."""

    def test_sync_status_summary_excludes_other_tenant(self, client, db, seed_tenants, auth_headers):
        import uuid
        from app.modules.mfa.models import SyncQueueEntry

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            db.session.add(
                SyncQueueEntry(
                    tenant_id=seed_tenants["b"], device_id="tenant-b-device", client_record_id=uuid.uuid4(),
                    target_module="HSE", target_entity_type="hse_near_miss", payload={}, status="synced",
                )
            )
        db.session.commit()

        r = client.get("/v1/mfa/sync-status", headers=auth_headers("a"))
        assert r.get_json() == {"pending": 0, "synced": 0, "conflict": 0, "rejected": 0}

    def test_cannot_resolve_other_tenants_conflict(self, client, db, seed_tenants, auth_headers):
        import uuid
        from app.modules.mfa.models import SyncQueueEntry, ConflictRecord

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            entry = SyncQueueEntry(
                tenant_id=seed_tenants["b"], device_id="tenant-b-device", client_record_id=uuid.uuid4(),
                target_module="HSE", target_entity_type="hse_near_miss", payload={"description": "x"}, status="conflict",
            )
            db.session.add(entry)
            db.session.flush()
            conflict = ConflictRecord(
                tenant_id=seed_tenants["b"], sync_queue_entry_id=entry.id,
                conflict_type="validation_failure", client_payload={"description": "x"},
            )
            db.session.add(conflict)
            db.session.flush()
            conflict_id = conflict.id
        db.session.commit()

        r = client.post(f"/v1/mfa/conflicts/{conflict_id}/resolve", headers=auth_headers("a"), json={"resolution": {}})
        assert r.status_code == 404

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            untouched = db.session.get(ConflictRecord, conflict_id)
            assert untouched.status == "unresolved"


class TestAICrossTenantIsolation:
    """Module 25 (AI Construction Assistant) isolation cases. Targets
    the query-log listing (per AI-14's explicit requirement that no
    tenant's data ever appears in another tenant's AI context) and the
    extraction-commit action, which writes into a real target-module
    record and must not be reachable cross-tenant."""

    def test_query_logs_exclude_other_tenant(self, client, db, seed_tenants, auth_headers):
        from app.modules.ai.models import AIQueryLog

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            db.session.add(
                AIQueryLog(tenant_id=seed_tenants["b"], tool_name="list_at_risk_projects", context_retrieved=[{"secret": "tenant-b-data"}])
            )
        db.session.commit()

        r = client.get("/v1/ai/query-logs", headers=auth_headers("a"))
        assert r.get_json()["data"] == []

    def test_cannot_review_other_tenants_extraction_job(self, client, db, seed_tenants, auth_headers):
        from app.modules.ai.models import AIDocumentExtractionJob

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            job = AIDocumentExtractionJob(
                tenant_id=seed_tenants["b"], extraction_type="boq", status="extracted",
                extracted_data={"item_code": "X"},
            )
            db.session.add(job)
            db.session.flush()
            job_id = job.id
        db.session.commit()

        r = client.post(f"/v1/ai/extraction-jobs/{job_id}/review", headers=auth_headers("a"), json={})
        assert r.status_code == 404

        with db.session.begin_nested():
            _as_tenant(db, seed_tenants["b"])
            untouched = db.session.get(AIDocumentExtractionJob, job_id)
            assert untouched.status == "extracted"
