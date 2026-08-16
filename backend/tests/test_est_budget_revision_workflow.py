"""
Tests for EST's Budget Revision workflow integration
(app/modules/est/services.py:create_budget_revision/finalize_budget_revision).

Regression coverage for a real budget-integrity gap found while
extending the Workflow Engine to a fourth module: every revision
self-approved immediately on creation (approved_by was always the
same actor who created it), directly mutating
CBSLineItem.budgeted_amount -- the same figure
app/commitments/services.py computes remaining budget against -- on
the say-so of a single user holding est:approve alone, despite
BudgetRevision being explicitly documented as "the only sanctioned
way to change an approved CBS baseline."
"""
import uuid

from sqlalchemy import text


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def _seed_approved_cbs(db, tenant_id, *, budgeted_amount=1000000):
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

    cbs_id, cbs_line_id = cbs.id, cbs_line.id
    db.session.commit()
    return cbs_id, cbs_line_id


class TestBudgetRevisionWithoutWorkflow:
    """Backward compatibility: a tenant that hasn't configured a
    workflow for ("est", "budget_revision") must see identical
    behavior to before this integration existed."""

    def test_revision_self_approves_and_applies_immediately(self, app, db, client, seed_tenants, auth_headers):
        cbs_id, cbs_line_id = _seed_approved_cbs(db, seed_tenants["a"], budgeted_amount=1000000)
        headers = auth_headers("a", permissions=["est:approve"])

        r = client.post(f"/v1/est/cost-breakdown-structures/{cbs_id}/budget-revisions", headers=headers, json={
            "cbs_line_item_id": str(cbs_line_id), "reason": "Scope increase", "revised_amount": "1200000",
        })
        assert r.status_code == 201
        assert r.get_json()["status"] == "approved"

        r2 = client.get(f"/v1/commitments/cbs-line-items/{cbs_line_id}/summary", headers=auth_headers("a", permissions=["fin:read"]))
        assert r2.get_json()["budgeted_amount"] == "1200000.0000"


class TestBudgetRevisionWithWorkflow:
    def _activate_workflow(self, client, headers, role_id):
        r = client.post("/v1/workflow/definitions", headers=headers, json={
            "module_name": "est", "entity_type": "budget_revision", "workflow_name": "Budget Revision Approval",
            "steps": [{"step_number": 1, "name": "Approver", "approver_type": "specific_role", "required_role_id": str(role_id)}],
        })
        definition_id = r.get_json()["id"]
        client.post(f"/v1/workflow/definitions/{definition_id}/activate", headers=headers)

    def _make_role(self, db, tenant_id):
        from app.models.core import Role

        _as_tenant(db, tenant_id)
        role = Role(tenant_id=tenant_id, name="Approver", permission_set=["est:approve", "fin:read", "workflow:approve", "workflow:admin"])
        db.session.add(role)
        db.session.flush()
        role_id = role.id
        db.session.commit()
        return role_id

    def test_revision_is_pending_and_budget_unchanged_until_approved(self, app, db, client, seed_tenants, auth_headers):
        role_id = self._make_role(db, seed_tenants["a"])
        cbs_id, cbs_line_id = _seed_approved_cbs(db, seed_tenants["a"], budgeted_amount=1000000)
        headers = auth_headers("a", permissions=["est:approve", "fin:read", "workflow:admin", "workflow:approve"], role_id=role_id)
        self._activate_workflow(client, headers, role_id)

        r = client.post(f"/v1/est/cost-breakdown-structures/{cbs_id}/budget-revisions", headers=headers, json={
            "cbs_line_item_id": str(cbs_line_id), "reason": "Scope increase", "revised_amount": "1500000",
        })
        assert r.status_code == 201
        assert r.get_json()["status"] == "pending"

        r2 = client.get(f"/v1/commitments/cbs-line-items/{cbs_line_id}/summary", headers=headers)
        assert r2.get_json()["budgeted_amount"] == "1000000.0000"  # unchanged

    def test_finalize_blocked_while_workflow_still_pending(self, app, db, client, seed_tenants, auth_headers):
        role_id = self._make_role(db, seed_tenants["a"])
        cbs_id, cbs_line_id = _seed_approved_cbs(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["est:approve", "fin:read", "workflow:admin", "workflow:approve"], role_id=role_id)
        self._activate_workflow(client, headers, role_id)

        r = client.post(f"/v1/est/cost-breakdown-structures/{cbs_id}/budget-revisions", headers=headers, json={
            "cbs_line_item_id": str(cbs_line_id), "reason": "Scope increase", "revised_amount": "1500000",
        })
        revision_id = r.get_json()["id"]

        r2 = client.post(f"/v1/est/budget-revisions/{revision_id}/finalize", headers=headers, json={})
        assert r2.status_code == 409

    def test_finalize_applies_the_mutation_once_workflow_approves(self, app, db, client, seed_tenants, auth_headers):
        role_id = self._make_role(db, seed_tenants["a"])
        cbs_id, cbs_line_id = _seed_approved_cbs(db, seed_tenants["a"], budgeted_amount=1000000)
        headers = auth_headers("a", permissions=["est:approve", "fin:read", "workflow:admin", "workflow:approve"], role_id=role_id)
        self._activate_workflow(client, headers, role_id)

        r = client.post(f"/v1/est/cost-breakdown-structures/{cbs_id}/budget-revisions", headers=headers, json={
            "cbs_line_item_id": str(cbs_line_id), "reason": "Scope increase", "revised_amount": "1500000",
        })
        revision_id = r.get_json()["id"]

        instances = client.get("/v1/workflow/instances?module_name=est&entity_type=budget_revision", headers=headers).get_json()["data"]
        instance_id = [i for i in instances if i["entity_id"] == revision_id][0]["id"]
        client.post(f"/v1/workflow/instances/{instance_id}/approve", headers=headers, json={})

        r2 = client.post(f"/v1/est/budget-revisions/{revision_id}/finalize", headers=headers, json={})
        assert r2.status_code == 200
        assert r2.get_json()["status"] == "approved"

        r3 = client.get(f"/v1/commitments/cbs-line-items/{cbs_line_id}/summary", headers=headers)
        assert r3.get_json()["budgeted_amount"] == "1500000.0000"

    def test_cannot_finalize_an_already_approved_revision(self, app, db, client, seed_tenants, auth_headers):
        cbs_id, cbs_line_id = _seed_approved_cbs(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["est:approve"])  # no workflow configured for this tenant

        r = client.post(f"/v1/est/cost-breakdown-structures/{cbs_id}/budget-revisions", headers=headers, json={
            "cbs_line_item_id": str(cbs_line_id), "reason": "No workflow configured", "revised_amount": "1100000",
        })
        revision_id = r.get_json()["id"]  # self-approved immediately, no workflow active

        r2 = client.post(f"/v1/est/budget-revisions/{revision_id}/finalize", headers=headers, json={})
        assert r2.status_code == 409
