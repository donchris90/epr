"""
Module 7 — Procurement (Code: PRC)
SRS Section 4.7.

Extends beyond simple purchase orders into full vendor lifecycle
management, tightly integrated with Estimating (for budget checks) and
Inventory (for receipt).

Key Data Entities (SRS 4.7): Vendor, RFQ, QuotationComparison,
PurchaseRequest, PurchaseOrder, Approval, GoodsReceiptNote,
InvoiceMatch, VendorPerformanceRecord, SupplierRating.

Design notes:
  - `QuotationComparison` (PRC-03) is a computed view over RFQQuotation
    rows, not a stored table -- see services.compare_quotations. There
    is nothing to persist that isn't already in the quotations
    themselves.
  - `cost_code` / `cbs_line_item_id` fields are loose references to
    app.modules.est's CBSLineItem (no FK). PRC reads that ID for
    display/traceability but never queries est_* tables directly
    (bounded-context discipline, SRS 3.3) -- remaining-budget checks
    (PRC-04, PRC-11) take the remaining budget as a value supplied by
    the caller, the same pattern used for EXE's contracted_quantity
    check.
  - `Approval` (the named entity) is implemented as POApprovalStep,
    following the same sequential, value-threshold-configurable pattern
    already used for TBM's ApprovalStep (SRS 4.2) -- multi-level
    approval workflows recur throughout the SRS and this is the third
    module to need one.
"""
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin, SoftDeleteMixin


VENDOR_STATUSES = ("active", "inactive")
RFQ_STATUSES = ("open", "closed")
RFQ_INVITATION_STATUSES = ("invited", "responded", "declined")
PR_STATUSES = ("draft", "submitted", "approved", "rejected", "converted")
PO_STATUSES = ("draft", "pending_approval", "approved", "issued", "closed", "cancelled")
PO_APPROVAL_STATUSES = ("pending", "approved", "rejected")
GRN_CONDITIONS = ("good", "damaged", "partial")
MATCH_STATUSES = ("pending", "matched", "discrepancy")


class Vendor(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin, SoftDeleteMixin):
    """PRC-01: vendor registration, including compliance document
    tracking via VendorComplianceDocument."""

    __tablename__ = "prc_vendors"

    name = db.Column(db.String(255), nullable=False)
    tax_registration_number = db.Column(db.String(64), nullable=True)
    banking_details = db.Column(JSONB, nullable=True)
    categories_supplied = db.Column(JSONB, nullable=True)  # list of strings
    status = db.Column(db.String(16), nullable=False, default="active")

    compliance_documents = relationship("VendorComplianceDocument", back_populates="vendor", cascade="all, delete-orphan")

    __table_args__ = (db.CheckConstraint(f"status IN {VENDOR_STATUSES}", name="ck_prc_vendors_status"),)


class VendorComplianceDocument(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """Backs PRC-01's "compliance document expiry" tracking and the
    business rule blocking PO issuance to a vendor with expired
    documents (SRS 4.7)."""

    __tablename__ = "prc_vendor_compliance_documents"

    vendor_id = db.Column(UUID(as_uuid=True), db.ForeignKey("prc_vendors.id"), nullable=False, index=True)
    document_id = db.Column(UUID(as_uuid=True), db.ForeignKey("documents.id"), nullable=True)
    doc_type = db.Column(db.String(64), nullable=False)  # e.g. "trade_license", "insurance"
    valid_until = db.Column(db.Date, nullable=True, index=True)

    vendor = relationship("Vendor", back_populates="compliance_documents")


class RFQ(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PRC-02: request for quotation to multiple vendors."""

    __tablename__ = "prc_rfqs"

    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    response_deadline = db.Column(db.DateTime(timezone=True), nullable=True)
    status = db.Column(db.String(16), nullable=False, default="open")

    invitations = relationship("RFQInvitation", back_populates="rfq", cascade="all, delete-orphan")
    quotations = relationship("RFQQuotation", back_populates="rfq", cascade="all, delete-orphan")

    __table_args__ = (db.CheckConstraint(f"status IN {RFQ_STATUSES}", name="ck_prc_rfqs_status"),)


class RFQInvitation(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    __tablename__ = "prc_rfq_invitations"

    rfq_id = db.Column(UUID(as_uuid=True), db.ForeignKey("prc_rfqs.id"), nullable=False, index=True)
    vendor_id = db.Column(UUID(as_uuid=True), db.ForeignKey("prc_vendors.id"), nullable=False, index=True)
    status = db.Column(db.String(16), nullable=False, default="invited")

    rfq = relationship("RFQ", back_populates="invitations")

    __table_args__ = (
        db.CheckConstraint(f"status IN {RFQ_INVITATION_STATUSES}", name="ck_prc_rfq_invitations_status"),
        db.UniqueConstraint("rfq_id", "vendor_id", name="uq_prc_rfq_invitations_pair"),
    )


class RFQQuotation(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """A vendor's response to an RFQ. PRC-03's Quotation Comparison is
    computed over these, not stored separately -- see services.py."""

    __tablename__ = "prc_rfq_quotations"

    rfq_id = db.Column(UUID(as_uuid=True), db.ForeignKey("prc_rfqs.id"), nullable=False, index=True)
    vendor_id = db.Column(UUID(as_uuid=True), db.ForeignKey("prc_vendors.id"), nullable=False, index=True)

    price = db.Column(db.Numeric(18, 4), nullable=False)
    lead_time_days = db.Column(db.Integer, nullable=True)
    payment_terms = db.Column(db.String(255), nullable=True)
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=True)

    rfq = relationship("RFQ", back_populates="quotations")

    __table_args__ = (db.UniqueConstraint("rfq_id", "vendor_id", name="uq_prc_rfq_quotations_pair"),)


class PurchaseRequest(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin, SoftDeleteMixin):
    """PRC-04: raised by site/project staff, validated against
    remaining CBS budget before submission (business rule, PRC-11)."""

    __tablename__ = "prc_purchase_requests"

    project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)
    cbs_line_item_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)  # est_cbs_line_items.id, loose ref
    requested_by = db.Column(UUID(as_uuid=True), nullable=True)

    description = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Numeric(18, 4), nullable=False)
    unit = db.Column(db.String(32), nullable=True)
    estimated_unit_cost = db.Column(db.Numeric(18, 4), nullable=True)
    estimated_total = db.Column(db.Numeric(18, 4), nullable=True)

    status = db.Column(db.String(16), nullable=False, default="draft")

    budget_override = db.Column(db.Boolean, nullable=False, default=False)
    budget_override_reason = db.Column(db.Text, nullable=True)
    budget_override_by = db.Column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (db.CheckConstraint(f"status IN {PR_STATUSES}", name="ck_prc_purchase_requests_status"),)


class PurchaseOrder(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin, SoftDeleteMixin):
    """PRC-05/06/12: generated from an approved PR or accepted
    quotation. `is_blanket` (PRC-12) marks a framework PO drawn down
    incrementally by multiple GoodsReceiptNotes."""

    __tablename__ = "prc_purchase_orders"

    purchase_request_id = db.Column(UUID(as_uuid=True), db.ForeignKey("prc_purchase_requests.id"), nullable=True)
    rfq_quotation_id = db.Column(UUID(as_uuid=True), db.ForeignKey("prc_rfq_quotations.id"), nullable=True)
    vendor_id = db.Column(UUID(as_uuid=True), db.ForeignKey("prc_vendors.id"), nullable=False, index=True)

    po_number = db.Column(db.String(128), nullable=False)
    status = db.Column(db.String(24), nullable=False, default="draft", index=True)
    total_value = db.Column(db.Numeric(18, 4), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="NGN")
    is_blanket = db.Column(db.Boolean, nullable=False, default=False)

    compliance_waiver = db.Column(db.Boolean, nullable=False, default=False)
    compliance_waiver_reason = db.Column(db.Text, nullable=True)
    compliance_waiver_by = db.Column(UUID(as_uuid=True), nullable=True)

    budget_override = db.Column(db.Boolean, nullable=False, default=False)
    budget_override_reason = db.Column(db.Text, nullable=True)
    budget_override_by = db.Column(UUID(as_uuid=True), nullable=True)

    lines = relationship("PurchaseOrderLine", back_populates="purchase_order", cascade="all, delete-orphan")
    approval_steps = relationship(
        "POApprovalStep", back_populates="purchase_order", order_by="POApprovalStep.step_order", cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.CheckConstraint(f"status IN {PO_STATUSES}", name="ck_prc_purchase_orders_status"),
        db.UniqueConstraint("tenant_id", "po_number", name="uq_prc_purchase_orders_tenant_number"),
    )


class PurchaseOrderLine(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """Line-item reference back to the originating BOQ/CBS item
    (PRC-05)."""

    __tablename__ = "prc_purchase_order_lines"

    purchase_order_id = db.Column(UUID(as_uuid=True), db.ForeignKey("prc_purchase_orders.id"), nullable=False, index=True)
    boq_item_id = db.Column(UUID(as_uuid=True), nullable=True)  # loose reference
    cbs_line_item_id = db.Column(UUID(as_uuid=True), nullable=True)  # loose reference
    # Loose reference to inv_material_items.id (Module 8) -- nullable
    # because not every PO line represents a trackable inventory
    # material (services, subcontractor labor, etc. have nothing to
    # receive into stock). When set, confirming the GRN this line
    # belongs to updates real Inventory stock -- see
    # services.py:confirm_goods_receipt.
    material_item_id = db.Column(UUID(as_uuid=True), nullable=True)

    description = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Numeric(18, 4), nullable=False)
    unit = db.Column(db.String(32), nullable=True)
    unit_price = db.Column(db.Numeric(18, 4), nullable=False)
    line_total = db.Column(db.Numeric(18, 4), nullable=False)

    # PRC-12: cumulative quantity drawn down against this line by GRNs,
    # for blanket/framework POs.
    quantity_received = db.Column(db.Numeric(18, 4), nullable=False, default=0)

    purchase_order = relationship("PurchaseOrder", back_populates="lines")


class POApprovalStep(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PRC-06: multi-level PO approval based on value thresholds --
    same sequential-approval pattern as TBM's ApprovalStep (SRS 4.2)."""

    __tablename__ = "prc_po_approval_steps"

    purchase_order_id = db.Column(UUID(as_uuid=True), db.ForeignKey("prc_purchase_orders.id"), nullable=False, index=True)
    step_order = db.Column(db.Integer, nullable=False)
    role_required = db.Column(db.String(128), nullable=False)
    value_threshold = db.Column(db.Numeric(18, 4), nullable=True)  # this step required above this PO value
    approver_id = db.Column(UUID(as_uuid=True), nullable=True)
    status = db.Column(db.String(16), nullable=False, default="pending")
    decided_at = db.Column(db.DateTime(timezone=True), nullable=True)
    comments = db.Column(db.Text, nullable=True)

    purchase_order = relationship("PurchaseOrder", back_populates="approval_steps")

    __table_args__ = (
        db.CheckConstraint(f"status IN {PO_APPROVAL_STATUSES}", name="ck_prc_po_approval_steps_status"),
        db.UniqueConstraint("purchase_order_id", "step_order", name="uq_prc_po_approval_steps_po_order"),
    )


class GoodsReceiptNote(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PRC-07: records receipt against a PO. Confirmation updates real
    Inventory stock (Module 8) for any line whose PO line has a
    material_item_id set -- see services.py:confirm_goods_receipt."""

    __tablename__ = "prc_goods_receipt_notes"

    purchase_order_id = db.Column(UUID(as_uuid=True), db.ForeignKey("prc_purchase_orders.id"), nullable=False, index=True)
    # Loose reference to inv_warehouses.id (Module 8) -- which
    # warehouse received the goods. Nullable: a GRN with no
    # inventory-tracked lines (material_item_id unset on every line)
    # has nothing to receive into stock and doesn't need one. Required
    # (validated in services.py, not here) the moment any line does.
    warehouse_id = db.Column(UUID(as_uuid=True), nullable=True)
    received_at = db.Column(db.DateTime(timezone=True), nullable=True)
    received_by = db.Column(UUID(as_uuid=True), nullable=True)
    status = db.Column(db.String(16), nullable=False, default="draft")  # draft | confirmed

    lines = relationship("GoodsReceiptLine", back_populates="grn", cascade="all, delete-orphan")

    __table_args__ = (db.CheckConstraint("status IN ('draft','confirmed')", name="ck_prc_grn_status"),)


class GoodsReceiptLine(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    __tablename__ = "prc_goods_receipt_lines"

    grn_id = db.Column(UUID(as_uuid=True), db.ForeignKey("prc_goods_receipt_notes.id"), nullable=False, index=True)
    po_line_id = db.Column(UUID(as_uuid=True), db.ForeignKey("prc_purchase_order_lines.id"), nullable=False, index=True)

    quantity_received = db.Column(db.Numeric(18, 4), nullable=False)
    condition = db.Column(db.String(16), nullable=False, default="good")
    discrepancy_notes = db.Column(db.Text, nullable=True)

    grn = relationship("GoodsReceiptNote", back_populates="lines")
    po_line = relationship("PurchaseOrderLine")

    __table_args__ = (db.CheckConstraint(f"condition IN {GRN_CONDITIONS}", name="ck_prc_grn_lines_condition"),)


class InvoiceMatch(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PRC-08: three-way match (PO, GRN, vendor invoice). Business
    rule: invoice payment (Module 17) is blocked until this is complete
    or an exception is explicitly approved."""

    __tablename__ = "prc_invoice_matches"

    purchase_order_id = db.Column(UUID(as_uuid=True), db.ForeignKey("prc_purchase_orders.id"), nullable=False, index=True)
    goods_receipt_note_id = db.Column(UUID(as_uuid=True), db.ForeignKey("prc_goods_receipt_notes.id"), nullable=True)

    vendor_invoice_reference = db.Column(db.String(128), nullable=False)
    invoice_amount = db.Column(db.Numeric(18, 4), nullable=False)
    po_amount = db.Column(db.Numeric(18, 4), nullable=False)
    grn_amount = db.Column(db.Numeric(18, 4), nullable=True)

    match_status = db.Column(db.String(16), nullable=False, default="pending")
    matched_at = db.Column(db.DateTime(timezone=True), nullable=True)

    exception_approved = db.Column(db.Boolean, nullable=False, default=False)
    exception_approved_by = db.Column(UUID(as_uuid=True), nullable=True)
    exception_reason = db.Column(db.Text, nullable=True)

    released_for_payment = db.Column(db.Boolean, nullable=False, default=False)

    __table_args__ = (db.CheckConstraint(f"match_status IN {MATCH_STATUSES}", name="ck_prc_invoice_matches_status"),)


class VendorPerformanceRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PRC-09: on-time delivery / quality rejection / price
    competitiveness tracked over time."""

    __tablename__ = "prc_vendor_performance_records"

    vendor_id = db.Column(UUID(as_uuid=True), db.ForeignKey("prc_vendors.id"), nullable=False, index=True)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)

    on_time_delivery_rate = db.Column(db.Numeric(5, 2), nullable=True)  # 0-100
    quality_rejection_rate = db.Column(db.Numeric(5, 2), nullable=True)  # 0-100
    price_competitiveness_score = db.Column(db.Numeric(5, 2), nullable=True)  # 0-100


class SupplierRating(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PRC-10: structured scorecard reviewable at contract renewal or
    annual vendor review."""

    __tablename__ = "prc_supplier_ratings"

    vendor_id = db.Column(UUID(as_uuid=True), db.ForeignKey("prc_vendors.id"), nullable=False, index=True)
    rating_period = db.Column(db.String(32), nullable=True)  # e.g. "2026-Q1", "2026-annual"
    scorecard = db.Column(JSONB, nullable=False, default=dict)  # {criterion: score, ...}
    overall_score = db.Column(db.Numeric(5, 2), nullable=True)
    reviewed_by = db.Column(UUID(as_uuid=True), nullable=True)
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
