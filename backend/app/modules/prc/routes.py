"""
Module 7 — Procurement (Code: PRC)
SRS Section 4.7 — Flask Blueprint. Base path: /v1/prc
"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.extensions import db
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import get_pagination_params, envelope

from app.modules.prc import services
from app.modules.prc.models import (
    Vendor,
    VendorComplianceDocument,
    RFQ,
    RFQInvitation,
    RFQQuotation,
    PurchaseRequest,
    PurchaseOrder,
    PurchaseOrderLine,
    POApprovalStep,
    GoodsReceiptNote,
    GoodsReceiptLine,
    VendorPerformanceRecord,
    SupplierRating,
)
from app.modules.prc.schemas import (
    VendorSchema,
    VendorComplianceDocumentSchema,
    RFQSchema,
    RFQInvitationSchema,
    RFQQuotationSchema,
    PurchaseRequestSchema,
    SubmitPurchaseRequestSchema,
    PurchaseOrderSchema,
    PurchaseOrderLineSchema,
    InitiatePOApprovalSchema,
    POApprovalStepSchema,
    POApprovalDecisionSchema,
    IssuePOSchema,
    GoodsReceiptNoteSchema,
    InvoiceMatchRequestSchema,
    InvoiceMatchSchema,
    MatchExceptionSchema,
    VendorPerformanceRecordSchema,
    SupplierRatingSchema,
)

bp = Blueprint("prc", __name__, url_prefix="/v1/prc")

vendor_schema = VendorSchema()
compliance_doc_schema = VendorComplianceDocumentSchema()
rfq_schema = RFQSchema()
invitation_schema = RFQInvitationSchema()
quotation_schema = RFQQuotationSchema()
pr_schema = PurchaseRequestSchema()
po_schema = PurchaseOrderSchema()
po_line_schema = PurchaseOrderLineSchema()
po_approval_schema = POApprovalDecisionSchema()
grn_schema = GoodsReceiptNoteSchema()
invoice_match_schema = InvoiceMatchSchema()
performance_schema = VendorPerformanceRecordSchema()
rating_schema = SupplierRatingSchema()
approval_step_schema = POApprovalStepSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_vendor_or_404(vendor_id) -> Vendor:
    v = Vendor.query.filter_by(id=vendor_id, tenant_id=g.tenant_id, deleted_at=None).first()
    if not v:
        raise APIError("Vendor not found", status=404)
    return v


def _get_rfq_or_404(rfq_id) -> RFQ:
    r = RFQ.query.filter_by(id=rfq_id, tenant_id=g.tenant_id).first()
    if not r:
        raise APIError("RFQ not found", status=404)
    return r


def _get_pr_or_404(pr_id) -> PurchaseRequest:
    pr = PurchaseRequest.query.filter_by(id=pr_id, tenant_id=g.tenant_id, deleted_at=None).first()
    if not pr:
        raise APIError("Purchase request not found", status=404)
    return pr


def _get_po_or_404(po_id) -> PurchaseOrder:
    po = PurchaseOrder.query.filter_by(id=po_id, tenant_id=g.tenant_id, deleted_at=None).first()
    if not po:
        raise APIError("Purchase order not found", status=404)
    return po


@bp.get("/health")
def health():
    return jsonify({"module": "prc", "name": "Procurement", "status": "ok"})


# --- Vendors (PRC-01) --------------------------------------------------------

@bp.post("/vendors")
@require_permission("prc:write")
def create_vendor():
    data = _load(vendor_schema)
    vendor = Vendor(tenant_id=g.tenant_id, **data)
    db.session.add(vendor)
    db.session.commit()
    return jsonify(vendor_schema.dump(vendor)), 201


@bp.get("/vendors")
@require_permission("prc:read")
def list_vendors():
    cursor, limit = get_pagination_params()
    vendors = Vendor.query.filter_by(tenant_id=g.tenant_id, deleted_at=None).limit(limit).all()
    return jsonify(envelope(vendor_schema.dump(vendors, many=True)))


@bp.post("/vendors/<uuid:vendor_id>/compliance-documents")
@require_permission("prc:write")
def add_compliance_document(vendor_id):
    vendor = _get_vendor_or_404(vendor_id)
    data = _load(compliance_doc_schema)
    doc = VendorComplianceDocument(tenant_id=g.tenant_id, vendor_id=vendor.id, **data)
    db.session.add(doc)
    db.session.commit()
    return jsonify(compliance_doc_schema.dump(doc)), 201


# --- RFQs & quotations (PRC-02, PRC-03) --------------------------------------

@bp.post("/rfqs")
@require_permission("prc:write")
def create_rfq():
    data = _load(rfq_schema)
    rfq = RFQ(tenant_id=g.tenant_id, **data)
    db.session.add(rfq)
    db.session.commit()
    return jsonify(rfq_schema.dump(rfq)), 201


@bp.post("/rfqs/<uuid:rfq_id>/invite")
@require_permission("prc:write")
def invite_vendor(rfq_id):
    rfq = _get_rfq_or_404(rfq_id)
    data = _load(invitation_schema)
    _get_vendor_or_404(data["vendor_id"])
    invitation = RFQInvitation(tenant_id=g.tenant_id, rfq_id=rfq.id, vendor_id=data["vendor_id"])
    db.session.add(invitation)
    db.session.commit()
    return jsonify(invitation_schema.dump(invitation)), 201


@bp.post("/rfqs/<uuid:rfq_id>/quotations")
@require_permission("prc:write")
def submit_quotation(rfq_id):
    rfq = _get_rfq_or_404(rfq_id)
    data = _load(quotation_schema)
    _get_vendor_or_404(data["vendor_id"])
    quotation = RFQQuotation(tenant_id=g.tenant_id, rfq_id=rfq.id, **data)
    db.session.add(quotation)
    db.session.commit()
    return jsonify(quotation_schema.dump(quotation)), 201


@bp.get("/rfqs/<uuid:rfq_id>/comparison")
@require_permission("prc:read")
def get_quotation_comparison(rfq_id):
    rfq = _get_rfq_or_404(rfq_id)
    return jsonify({"rfq_id": str(rfq.id), "quotations": services.compare_quotations(rfq)})


# --- Purchase requests (PRC-04, PRC-11, business rule) -----------------------

@bp.post("/purchase-requests")
@require_permission("prc:write")
def create_purchase_request():
    data = _load(pr_schema)
    pr = PurchaseRequest(tenant_id=g.tenant_id, requested_by=g.user_id, **data)
    db.session.add(pr)
    db.session.commit()
    return jsonify(pr_schema.dump(pr)), 201


@bp.get("/purchase-requests")
@require_permission("prc:read")
def list_purchase_requests():
    query = PurchaseRequest.query.filter_by(tenant_id=g.tenant_id, deleted_at=None)
    status = request.args.get("status")
    if status:
        query = query.filter_by(status=status)
    prs = query.all()
    return jsonify(envelope(pr_schema.dump(prs, many=True)))


@bp.post("/purchase-requests/<uuid:pr_id>/submit")
@require_permission("prc:write")
def submit_purchase_request(pr_id):
    pr = _get_pr_or_404(pr_id)
    data = _load(SubmitPurchaseRequestSchema())
    try:
        pr = services.submit_purchase_request(
            pr,
            remaining_budget=data["remaining_budget"],
            override=data["override"],
            override_reason=data.get("override_reason"),
            override_by=g.user_id,
        )
    except APIError as err:
        # Surface budget-breach detail even on failure, since the
        # frontend needs it to offer "resubmit with override".
        raise err
    return jsonify(pr_schema.dump(pr))


@bp.post("/purchase-requests/<uuid:pr_id>/approve")
@require_permission("prc:approve")
def approve_purchase_request(pr_id):
    pr = _get_pr_or_404(pr_id)
    pr = services.approve_purchase_request(pr, actor_id=g.user_id)
    return jsonify(pr_schema.dump(pr))


# --- Purchase orders (PRC-05, PRC-06, PRC-12) ---------------------------------

@bp.post("/purchase-orders")
@require_permission("prc:write")
def create_purchase_order():
    data = _load(po_schema)
    lines_data = data.pop("lines", [])
    _get_vendor_or_404(data["vendor_id"])

    po = PurchaseOrder(tenant_id=g.tenant_id, **data)
    db.session.add(po)
    db.session.flush()

    for line_data in lines_data:
        line_total = line_data["quantity"] * line_data["unit_price"]
        db.session.add(PurchaseOrderLine(tenant_id=g.tenant_id, purchase_order_id=po.id, line_total=line_total, **line_data))

    db.session.commit()
    return jsonify(po_schema.dump(po)), 201


@bp.get("/purchase-orders")
@require_permission("prc:read")
def list_purchase_orders():
    query = PurchaseOrder.query.filter_by(tenant_id=g.tenant_id, deleted_at=None)
    status = request.args.get("status")
    if status:
        query = query.filter_by(status=status)
    pos = query.all()
    return jsonify(envelope(po_schema.dump(pos, many=True)))


@bp.get("/purchase-orders/<uuid:po_id>")
@require_permission("prc:read")
def get_purchase_order(po_id):
    po = _get_po_or_404(po_id)
    body = po_schema.dump(po)
    body["line_items"] = po_line_schema.dump(po.lines, many=True)

    from app.modules.prc.models import InvoiceMatch

    latest_match = (
        InvoiceMatch.query.filter_by(purchase_order_id=po_id, tenant_id=g.tenant_id)
        .order_by(InvoiceMatch.created_at.desc())
        .first()
    )
    body["latest_match"] = invoice_match_schema.dump(latest_match) if latest_match else None
    body["approval_steps"] = approval_step_schema.dump(po.approval_steps, many=True)

    return jsonify(body)


@bp.post("/purchase-orders/<uuid:po_id>/approval-workflow/initiate")
@require_permission("prc:approve")
def initiate_po_approval(po_id):
    po = _get_po_or_404(po_id)
    data = _load(InitiatePOApprovalSchema())
    po = services.initiate_po_approval(po, thresholds=data["thresholds"])
    return jsonify(po_schema.dump(po))


@bp.post("/po-approval-steps/<uuid:step_id>/decide")
@require_permission("prc:approve")
def decide_po_approval_step(step_id):
    step = POApprovalStep.query.filter_by(id=step_id, tenant_id=g.tenant_id).first()
    if not step:
        raise APIError("Approval step not found", status=404)

    data = _load(po_approval_schema)
    step = services.decide_po_approval_step(
        step, decision=data["decision"], approver_id=g.user_id, comments=data.get("comments")
    )
    return jsonify({"status": step.status, "purchase_order_status": step.purchase_order.status})


@bp.post("/purchase-orders/<uuid:po_id>/issue")
@require_permission("prc:approve")
def issue_purchase_order(po_id):
    po = _get_po_or_404(po_id)
    data = _load(IssuePOSchema())
    po = services.issue_purchase_order(
        po, waiver=data["waiver"], waiver_reason=data.get("waiver_reason"), waiver_by=g.user_id
    )
    return jsonify(po_schema.dump(po))


# --- Goods receipt (PRC-07, PRC-12) ------------------------------------------

@bp.post("/goods-receipt-notes")
@require_permission("prc:write")
def create_grn():
    data = _load(grn_schema)
    lines_data = data.pop("lines")
    po = _get_po_or_404(data["purchase_order_id"])

    grn = GoodsReceiptNote(tenant_id=g.tenant_id, purchase_order_id=po.id, received_by=g.user_id, **{
        k: v for k, v in data.items() if k != "purchase_order_id"
    })
    db.session.add(grn)
    db.session.flush()

    for line_data in lines_data:
        db.session.add(GoodsReceiptLine(tenant_id=g.tenant_id, grn_id=grn.id, **line_data))

    db.session.commit()
    return jsonify(grn_schema.dump(grn)), 201


@bp.post("/goods-receipt-notes/<uuid:grn_id>/confirm")
@require_permission("prc:write")
def confirm_grn(grn_id):
    grn = GoodsReceiptNote.query.filter_by(id=grn_id, tenant_id=g.tenant_id).first()
    if not grn:
        raise APIError("Goods receipt note not found", status=404)
    grn = services.confirm_goods_receipt(grn)
    return jsonify(grn_schema.dump(grn))


# --- Three-way invoice matching (PRC-08, business rule) -----------------------

@bp.post("/purchase-orders/<uuid:po_id>/invoice-match")
@require_permission("prc:write")
def create_invoice_match(po_id):
    po = _get_po_or_404(po_id)
    data = _load(InvoiceMatchRequestSchema())
    match = services.perform_invoice_match(po, **data)
    return jsonify(invoice_match_schema.dump(match)), 201


@bp.post("/invoice-matches/<uuid:match_id>/approve-exception")
@require_permission("prc:approve")
def approve_match_exception(match_id):
    from app.modules.prc.models import InvoiceMatch

    match = InvoiceMatch.query.filter_by(id=match_id, tenant_id=g.tenant_id).first()
    if not match:
        raise APIError("Invoice match not found", status=404)

    data = _load(MatchExceptionSchema())
    match = services.approve_match_exception(match, approved_by=g.user_id, reason=data["reason"])
    return jsonify(invoice_match_schema.dump(match))


# --- Vendor performance & ratings (PRC-09, PRC-10) -----------------------------

@bp.post("/vendors/<uuid:vendor_id>/performance-records")
@require_permission("prc:write")
def add_performance_record(vendor_id):
    vendor = _get_vendor_or_404(vendor_id)
    data = _load(performance_schema)
    record = VendorPerformanceRecord(tenant_id=g.tenant_id, vendor_id=vendor.id, **data)
    db.session.add(record)
    db.session.commit()
    return jsonify(performance_schema.dump(record)), 201


@bp.post("/vendors/<uuid:vendor_id>/ratings")
@require_permission("prc:write")
def add_supplier_rating(vendor_id):
    vendor = _get_vendor_or_404(vendor_id)
    data = _load(rating_schema)
    rating = SupplierRating(tenant_id=g.tenant_id, vendor_id=vendor.id, reviewed_by=g.user_id, **data)
    db.session.add(rating)
    db.session.commit()
    return jsonify(rating_schema.dump(rating)), 201
