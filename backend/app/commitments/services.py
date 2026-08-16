"""
Commitment accounting -- tracks approved-but-not-yet-invoiced spend
against budget, distinct from both the budget itself and actual
invoiced spend. A real, previously-missing gap: PRC's own
submit_purchase_request docstring said remaining budget is "supplied
by the caller, not looked up here" -- meaning nothing in this
codebase ever actually computed it. This is that computation.

Deliberately no new table. Committed spend is derived live from
existing source-of-truth data (PurchaseOrder + PurchaseOrderLine),
not a denormalized ledger that would need to be kept in sync and
could drift out of date -- the same "reuse over redesign" discipline
followed throughout this codebase (see e.g. the Subcontractor
Portal's module docstring for the same principle applied elsewhere).

Scope, stated honestly: this computes *committed* spend (from issued
Purchase Orders) against budget. It does NOT also net out *actual*
invoiced spend from Accounts Payable -- AP invoices in this schema
reference a whole Purchase Order (fin_ap_invoices.source_reference),
not a specific PO line or CBS code, so apportioning an invoice back to
one CBS line when a PO spans several would require an allocation rule
this codebase doesn't have and this pass doesn't invent one for. What
this answers honestly and well: "how much of this budget line is
already spoken for by issued POs, whether or not they've been paid
yet" -- which is what "Commitments" means in cost control, and is a
real, complete answer to that specific question.
"""
from app.modules.est.models import CBSLineItem


# PO statuses that represent a real, binding commitment -- draft and
# pending_approval POs aren't yet commitments (they could still be
# rejected or changed before issue), and cancelled POs never were.
COMMITTED_PO_STATUSES = ("approved", "issued", "closed")


def get_commitment_summary(tenant_id, cbs_line_item_id):
    """Returns None if there's no such CBS line item in this tenant --
    callers (e.g. PRC's submit_purchase_request) should treat that the
    same as "nothing to check against" rather than an error, since a
    Purchase Request with no cbs_line_item_id set at all is a normal,
    valid state in this codebase (the field is nullable)."""
    if not cbs_line_item_id:
        return None

    cbs_line = CBSLineItem.query.filter_by(id=cbs_line_item_id, tenant_id=tenant_id).first()
    if not cbs_line:
        return None

    committed_amount = _committed_amount_for_cbs_line(tenant_id, cbs_line_item_id)
    budgeted_amount = cbs_line.budgeted_amount
    remaining_amount = budgeted_amount - committed_amount

    return {
        "cbs_line_item_id": cbs_line_item_id,
        "budgeted_amount": budgeted_amount,
        "committed_amount": committed_amount,
        "remaining_amount": remaining_amount,
    }


def _committed_amount_for_cbs_line(tenant_id, cbs_line_item_id):
    from sqlalchemy import func
    from app.extensions import db
    from app.modules.prc.models import PurchaseOrder, PurchaseOrderLine

    total = (
        db.session.query(func.coalesce(func.sum(PurchaseOrderLine.line_total), 0))
        .join(PurchaseOrder, PurchaseOrderLine.purchase_order_id == PurchaseOrder.id)
        .filter(
            PurchaseOrderLine.tenant_id == tenant_id,
            PurchaseOrderLine.cbs_line_item_id == cbs_line_item_id,
            PurchaseOrder.tenant_id == tenant_id,
            PurchaseOrder.status.in_(COMMITTED_PO_STATUSES),
            PurchaseOrder.deleted_at.is_(None),
        )
        .scalar()
    )
    return total
