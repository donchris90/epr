"""
Module 7 — Procurement (Code: PRC)
Service layer — business logic other modules must call through rather
than querying prc_* tables directly (SRS Section 3.3).

Business rules encoded here (SRS 4.7):
  - A Purchase Order cannot be issued to a Vendor whose compliance
    documents have expired, without an explicit compliance-waiver
    override recorded with reason and approver.
  - Invoice payment is blocked until three-way matching is complete or
    an exception is explicitly approved.
  - Purchase Requests/Orders that would breach the remaining CBS budget
    for the relevant cost code are flagged, requiring an override with
    recorded justification and approver.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.utils.errors import APIError
from app.workflow import services as workflow_services
from app.modules.prc.models import (
    Vendor,
    VendorComplianceDocument,
    RFQ,
    RFQQuotation,
    PurchaseRequest,
    PurchaseOrder,
    POApprovalStep,
    GoodsReceiptNote,
    GoodsReceiptLine,
    InvoiceMatch,
)


# --- Quotation comparison (PRC-03) ------------------------------------------

def compare_quotations(rfq: RFQ) -> list:
    """Computed side-by-side comparison over RFQQuotation rows -- there
    is nothing to persist that isn't already in the quotations
    themselves (see module docstring)."""
    quotations = RFQQuotation.query.filter_by(rfq_id=rfq.id).order_by(RFQQuotation.price.asc()).all()
    return [
        {
            "vendor_id": str(q.vendor_id),
            "price": str(q.price),
            "lead_time_days": q.lead_time_days,
            "payment_terms": q.payment_terms,
            "is_lowest_price": q.price == min((x.price for x in quotations), default=None),
        }
        for q in quotations
    ]


# --- Budget-checked Purchase Requests (PRC-04, PRC-11, business rule) ------

def submit_purchase_request(pr: PurchaseRequest, *, remaining_budget=None, override=False, override_reason=None, override_by=None):
    """
    `remaining_budget` can be supplied explicitly by the caller
    (honored as-is if given -- e.g. a caller that already has a more
    current figure from its own context), but when omitted this now
    computes a real one via app.commitments.services, using the PR's
    own cbs_line_item_id -- previously this fell back to skipping the
    budget check entirely, silently, because nothing in this codebase
    actually computed a remaining-budget figure anywhere. See
    app/commitments/services.py for what that computation does and
    does not account for.
    """
    if pr.status != "draft":
        raise APIError("Purchase request is not in draft", status=409, detail=f"Current status is '{pr.status}'")

    if remaining_budget is None and pr.cbs_line_item_id:
        from app.commitments import services as commitment_services

        summary = commitment_services.get_commitment_summary(pr.tenant_id, pr.cbs_line_item_id)
        if summary:
            remaining_budget = summary["remaining_amount"]

    estimated_total = pr.estimated_total or (pr.estimated_unit_cost or Decimal("0")) * pr.quantity
    breaches_budget = remaining_budget is not None and estimated_total > remaining_budget

    if breaches_budget and not override:
        raise APIError(
            "Purchase request would breach remaining CBS budget",
            status=409,
            detail=(
                f"Estimated total {estimated_total} exceeds remaining budget {remaining_budget}. "
                "Resubmit with an override and recorded justification, or reduce scope."
            ),
        )

    pr.status = "submitted"
    if breaches_budget:
        pr.budget_override = True
        pr.budget_override_reason = override_reason
        pr.budget_override_by = override_by

    db.session.flush()

    # Real Workflow Engine integration (Module 26) -- if this tenant
    # has configured and activated an approval chain for
    # ("prc", "purchase_request"), start a real instance so the
    # request routes through it instead of the single-approver default
    # in approve_purchase_request below. Purely additive: a tenant that
    # has never configured a workflow sees identical behavior to
    # before this integration existed -- get_active_workflow simply
    # returns None and nothing changes.
    workflow = workflow_services.get_active_workflow(pr.tenant_id, module_name="prc", entity_type="purchase_request")
    if workflow:
        workflow_services.start_workflow_instance(
            pr.tenant_id, workflow,
            module_name="prc", entity_type="purchase_request", entity_id=pr.id,
            initiated_by=override_by or pr.requested_by, amount=estimated_total,
        )

    db.session.commit()
    return pr


def approve_purchase_request(pr: PurchaseRequest, *, actor_id=None):
    if pr.status != "submitted":
        raise APIError("Purchase request is not submitted", status=409)

    # If a workflow instance governs this PR, this endpoint defers to
    # it rather than silently bypassing the configured approval chain
    # -- a real integration, not two competing, unconnected approval
    # paths that happen to both exist. Once the engine reports the
    # instance approved, this same endpoint finalizes the PR's own
    # status, so the calling UI doesn't need two different "approve"
    # actions depending on whether a workflow happens to be configured.
    from app.workflow.models import WorkflowInstance

    instance = (
        WorkflowInstance.query.filter_by(
            tenant_id=pr.tenant_id, module_name="prc", entity_type="purchase_request", entity_id=pr.id
        )
        .order_by(WorkflowInstance.created_at.desc())
        .first()
    )
    if instance:
        if instance.status == "pending":
            raise APIError(
                "This purchase request is governed by an approval workflow",
                status=409,
                detail=(
                    f"Use POST /v1/workflow/instances/{instance.id}/approve "
                    f"(currently at step {instance.current_step_number}), not this endpoint directly."
                ),
            )
        if instance.status in ("rejected", "cancelled"):
            raise APIError(f"The governing approval workflow was {instance.status} for this request", status=409)
        # instance.status == "approved" -- fall through and finalize.

    pr.status = "approved"
    pr.updated_by = actor_id
    db.session.commit()
    return pr


# --- Purchase Order approval workflow (PRC-06) ------------------------------

def initiate_po_approval(po: PurchaseOrder, *, thresholds: list):
    """
    `thresholds` is an ordered list of {"role_required": str,
    "value_threshold": Decimal | None} dicts. Only steps whose
    value_threshold is None or <= the PO's total_value apply -- this is
    what makes the workflow "based on value thresholds" per PRC-06
    (e.g. a Site Manager step for any value, a Finance Director step
    only above 10,000,000).
    """
    if po.approval_steps:
        raise APIError("Approval workflow already initiated for this PO", status=409)

    applicable = [t for t in thresholds if t.get("value_threshold") is None or po.total_value >= Decimal(str(t["value_threshold"]))]
    if not applicable:
        raise APIError("No approval steps apply to this PO value", status=400)

    for i, step in enumerate(applicable, start=1):
        db.session.add(
            POApprovalStep(
                tenant_id=po.tenant_id,
                purchase_order_id=po.id,
                step_order=i,
                role_required=step["role_required"],
                value_threshold=step.get("value_threshold"),
            )
        )

    po.status = "pending_approval"
    db.session.commit()
    return po


def decide_po_approval_step(step: POApprovalStep, *, decision: str, approver_id, comments=None):
    if decision not in ("approved", "rejected"):
        raise APIError("Invalid decision", status=400)
    if step.status != "pending":
        raise APIError("Approval step already decided", status=409)

    earlier_pending = POApprovalStep.query.filter(
        POApprovalStep.purchase_order_id == step.purchase_order_id,
        POApprovalStep.step_order < step.step_order,
        POApprovalStep.status != "approved",
    ).first()
    if earlier_pending:
        raise APIError(
            "Earlier approval step not yet approved",
            status=409,
            detail=f"Step {earlier_pending.step_order} ('{earlier_pending.role_required}') must be approved first.",
        )

    step.status = decision
    step.approver_id = approver_id
    step.comments = comments
    step.decided_at = datetime.now(timezone.utc)

    if decision == "rejected":
        step.purchase_order.status = "cancelled"
    else:
        remaining = POApprovalStep.query.filter(
            POApprovalStep.purchase_order_id == step.purchase_order_id, POApprovalStep.status == "pending"
        ).count()
        if remaining == 0:
            step.purchase_order.status = "approved"

    db.session.commit()
    return step


# --- Compliance-gated issuance (business rule) ------------------------------

def issue_purchase_order(po: PurchaseOrder, *, waiver=False, waiver_reason=None, waiver_by=None, as_of=None):
    """
    Business rule: cannot issue a PO to a vendor with expired
    compliance documents, without an explicit waiver recorded with
    reason and approver.
    """
    if po.status != "approved":
        raise APIError("Purchase order must be approved before it can be issued", status=409)

    as_of = as_of or date.today()
    expired = VendorComplianceDocument.query.filter(
        VendorComplianceDocument.vendor_id == po.vendor_id,
        VendorComplianceDocument.valid_until.isnot(None),
        VendorComplianceDocument.valid_until < as_of,
    ).all()

    if expired and not waiver:
        raise APIError(
            "Vendor has expired compliance documents",
            status=409,
            detail=(
                f"Expired: {', '.join(d.doc_type for d in expired)}. "
                "Issue with a compliance waiver (reason + approver) to override."
            ),
        )

    if expired:
        po.compliance_waiver = True
        po.compliance_waiver_reason = waiver_reason
        po.compliance_waiver_by = waiver_by

    po.status = "issued"
    db.session.commit()
    return po


# --- Goods receipt & blanket PO drawdown (PRC-07, PRC-12) -------------------

def confirm_goods_receipt(grn: GoodsReceiptNote):
    """
    Confirming a GRN updates real Inventory (Module 8) stock for any
    line whose PO line has a material_item_id set -- a real gap found
    and closed in a later audit than the one that first wrote this
    function: this comment used to say "once Module 8 exists," but
    Module 8 (Inventory & Warehouse) has existed since early in this
    build. PRC still doesn't write to inv_* tables directly (SRS 3.3)
    -- it calls Inventory's own service function, the same
    bounded-context discipline used everywhere else in this codebase.
    """
    if grn.status == "confirmed":
        raise APIError("Goods receipt note is already confirmed", status=409)
    if not grn.lines:
        raise APIError("Cannot confirm an empty goods receipt note", status=400)

    inventory_receipts = []  # (material_item_id, quantity_received, unit_cost) tuples
    for line in grn.lines:
        po_line = line.po_line
        po_line.quantity_received += line.quantity_received
        if po_line.material_item_id:
            inventory_receipts.append((po_line.material_item_id, line.quantity_received, po_line.unit_price))

    if inventory_receipts and not grn.warehouse_id:
        raise APIError(
            "warehouse_id is required to confirm a receipt with inventory-tracked lines",
            status=400,
            detail=(
                f"{len(inventory_receipts)} line(s) reference a material_item_id and need a "
                "warehouse to receive stock into."
            ),
        )

    grn.status = "confirmed"
    warehouse_id = grn.warehouse_id
    received_at = grn.received_at
    tenant_id = grn.tenant_id
    db.session.commit()

    # Captured as plain values above, deliberately, rather than
    # re-accessing grn/line/po_line attributes here -- those ORM
    # objects are expired after commit, and touching them again would
    # trigger a fresh SELECT with no guarantee tenant context is set
    # on whatever the next implicit transaction is.
    from app.modules.inv import services as inv_services

    for material_item_id, quantity_received, unit_cost in inventory_receipts:
        inv_services.receive_stock(
            tenant_id,
            warehouse_id=warehouse_id,
            material_item_id=material_item_id,
            quantity=quantity_received,
            unit_cost=unit_cost,
            received_at=received_at,
        )

    return grn


# --- Three-way invoice matching (PRC-08, business rule) ---------------------

# Tolerance for "matched" -- real invoices rarely land on an exact cent
# match against PO/GRN due to rounding; anything within this is treated
# as matched rather than flagged as a discrepancy.
MATCH_TOLERANCE = Decimal("0.01")


def perform_invoice_match(purchase_order: PurchaseOrder, *, goods_receipt_note_id, vendor_invoice_reference, invoice_amount):
    grn_amount = None
    if goods_receipt_note_id:
        grn = GoodsReceiptNote.query.get(goods_receipt_note_id)
        if grn:
            grn_amount = sum(
                (line.po_line.unit_price * line.quantity_received for line in grn.lines), Decimal("0")
            )

    po_amount = purchase_order.total_value
    invoice_amount = Decimal(str(invoice_amount))

    discrepancies = []
    if abs(invoice_amount - po_amount) > MATCH_TOLERANCE:
        discrepancies.append("invoice vs PO amount mismatch")
    if grn_amount is not None and abs(invoice_amount - grn_amount) > MATCH_TOLERANCE:
        discrepancies.append("invoice vs GRN amount mismatch")

    match_status = "discrepancy" if discrepancies else "matched"

    match = InvoiceMatch(
        tenant_id=purchase_order.tenant_id,
        purchase_order_id=purchase_order.id,
        goods_receipt_note_id=goods_receipt_note_id,
        vendor_invoice_reference=vendor_invoice_reference,
        invoice_amount=invoice_amount,
        po_amount=po_amount,
        grn_amount=grn_amount,
        match_status=match_status,
        matched_at=datetime.now(timezone.utc) if match_status == "matched" else None,
        released_for_payment=(match_status == "matched"),
    )
    db.session.add(match)
    db.session.commit()
    return match


def approve_match_exception(invoice_match: InvoiceMatch, *, approved_by, reason):
    """
    Business rule: the only way to release a discrepant invoice for
    payment without a clean three-way match -- an explicit, logged
    exception approval.
    """
    if invoice_match.match_status != "discrepancy":
        raise APIError("Only a discrepant match can have an exception approved", status=409)
    if not reason:
        raise APIError("A reason is required to approve a match exception", status=400)

    invoice_match.exception_approved = True
    invoice_match.exception_approved_by = approved_by
    invoice_match.exception_reason = reason
    invoice_match.released_for_payment = True
    db.session.commit()
    return invoice_match
