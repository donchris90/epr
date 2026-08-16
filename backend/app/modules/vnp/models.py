"""
Module 23 — Vendor Portal (Code: VNP)
SRS Section 4.23.

Gives suppliers and subcontractors self-service visibility into orders
and payment status, reducing procurement administrative overhead.

Key Data Entities (SRS 4.23): VendorPortalUser -- otherwise reads/writes
against Module 7 (Procurement) and Module 12 (Subcontractor Management)
entities with vendor-scoped access.

Design notes:
  - Unlike Module 22's many-to-many client-to-project scoping, a vendor
    user belongs to exactly ONE vendor (`VendorPortalUser.vendor_id`),
    so the defense-in-depth check here is simpler: does the
    PurchaseOrder/RFQ/invoice being accessed actually belong to THIS
    user's vendor. Still enforced the same way as Module 22's client
    check -- as an unconditional first line in every service function,
    independent of whatever the caller's permission grant says.
  - `OrderAcknowledgment` and `VendorInvoiceUpload` are not in the
    SRS's named entity list but are what VNP-01 and VNP-03 need to
    exist at all: an acknowledgment and an invoice upload are both
    facts with their own timestamp and state, not something that can
    just live as a field on Module 7's PurchaseOrder.
  - `VendorBankingChangeRequest` is not in the SRS's named entity list
    either, but is the entire mechanism the business rule depends on:
    "a vendor-submitted banking-detail change requires internal Finance
    approval before it can be used for payment." A vendor's submission
    creates a PENDING request; the live PRC Vendor.banking_details
    field is untouched until a distinct, internal-only approval action
    writes to it. Module 7's Vendor model gets a payment-redirection
    fraud vector closed by construction: there is no path from a
    vendor-portal submission directly to the field actual payments are
    computed against. VNP-02 (submit quotes) doesn't need a new table
    at all -- it's a vendor-scoped write to Module 7's existing
    RFQQuotation, gated by the same defense-in-depth ownership check.
"""
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin


INVOICE_UPLOAD_STATUSES = ("submitted", "matched", "rejected")
BANKING_CHANGE_STATUSES = ("pending", "approved", "rejected")


class VendorPortalUser(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """VNP's one named entity -- a portal login scoped to exactly one
    vendor (Module 7's Vendor, loose reference)."""

    __tablename__ = "vnp_portal_users"

    vendor_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)  # prc_vendors.id, loose reference
    email = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    __table_args__ = (db.UniqueConstraint("tenant_id", "email", name="uq_vnp_portal_users_tenant_email"),)


class OrderAcknowledgment(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """VNP-01: a vendor's electronic acknowledgment of a received
    Purchase Order, with a vendor-committed expected delivery date."""

    __tablename__ = "vnp_order_acknowledgments"

    vendor_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("vnp_portal_users.id"), nullable=False, index=True)
    purchase_order_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)  # prc_purchase_orders.id, loose ref
    acknowledged_at = db.Column(db.DateTime(timezone=True), nullable=True)
    expected_delivery_date = db.Column(db.Date, nullable=True)

    __table_args__ = (
        db.UniqueConstraint("purchase_order_id", name="uq_vnp_order_ack_po"),
    )


class VendorInvoiceUpload(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """VNP-03: an invoice a vendor submits against a received PO
    (Module 7) or a subcontract payment certificate (Module 12) --
    exactly one of the two references is set."""

    __tablename__ = "vnp_invoice_uploads"

    vendor_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("vnp_portal_users.id"), nullable=False, index=True)
    purchase_order_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)  # prc_purchase_orders.id, loose ref
    subcontract_certificate_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)  # sub_payment_certificates.id, loose ref

    invoice_document_id = db.Column(UUID(as_uuid=True), db.ForeignKey("documents.id"), nullable=True)
    invoice_number = db.Column(db.String(128), nullable=False)
    amount = db.Column(db.Numeric(18, 4), nullable=False)
    uploaded_at = db.Column(db.DateTime(timezone=True), nullable=True)
    status = db.Column(db.String(16), nullable=False, default="submitted")

    __table_args__ = (
        db.CheckConstraint(f"status IN {INVOICE_UPLOAD_STATUSES}", name="ck_vnp_invoice_upload_status"),
        db.CheckConstraint(
            "(purchase_order_id IS NOT NULL AND subcontract_certificate_id IS NULL) OR "
            "(purchase_order_id IS NULL AND subcontract_certificate_id IS NOT NULL)",
            name="ck_vnp_invoice_upload_exactly_one_reference",
        ),
    )


class VendorBankingChangeRequest(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """VNP-05: business rule -- a vendor-submitted banking-detail
    change is staged HERE and requires internal Finance approval before
    it can be applied to Module 7's live Vendor record. See module
    docstring for why this exists as its own table rather than a
    directly-editable Vendor field."""

    __tablename__ = "vnp_banking_change_requests"

    vendor_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("vnp_portal_users.id"), nullable=False, index=True)
    vendor_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)  # prc_vendors.id, loose reference

    proposed_banking_details = db.Column(JSONB, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="pending")
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    reviewed_by = db.Column(UUID(as_uuid=True), nullable=True)
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)

    __table_args__ = (db.CheckConstraint(f"status IN {BANKING_CHANGE_STATUSES}", name="ck_vnp_banking_change_status"),)
