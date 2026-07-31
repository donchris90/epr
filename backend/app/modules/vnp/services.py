"""
Module 23 — Vendor Portal (Code: VNP)
Service layer — business logic other modules must call through rather
than querying vnp_* tables directly (SRS Section 3.3).

Business rule (SRS 4.23): a vendor-submitted banking-detail change
requires internal Finance approval before it can be used for payment,
as a fraud-prevention control against payment-redirection attacks.
`submit_banking_change` never touches Module 7's live Vendor record;
only `approve_banking_change` does, and only after an explicit,
attributable internal approval call.

Every function here also enforces vendor-ownership as an unconditional
first check (assert_vendor_owns_purchase_order /
assert_vendor_invited_to_rfq), independent of the caller's permission
grant -- the same defense-in-depth pattern as Module 22's client-scope
check.
"""
from datetime import datetime, timezone

from app.extensions import db
from app.utils.errors import APIError
from app.modules.vnp.models import VendorPortalUser, OrderAcknowledgment, VendorInvoiceUpload, VendorBankingChangeRequest


# --- Defense-in-depth ownership checks ------------------------------------------

def assert_vendor_owns_purchase_order(tenant_id, *, vendor_user: VendorPortalUser, purchase_order_id):
    from app.modules.prc.models import PurchaseOrder

    po = PurchaseOrder.query.filter_by(id=purchase_order_id, tenant_id=tenant_id).first()
    if not po or po.vendor_id != vendor_user.vendor_id:
        raise APIError("This purchase order does not belong to your organization", status=403)
    return po


def assert_vendor_invited_to_rfq(tenant_id, *, vendor_user: VendorPortalUser, rfq_id):
    """VNP-02: a vendor may only quote on an RFQ they were actually
    invited to -- not any RFQ that happens to exist in the tenant."""
    from app.modules.prc.models import RFQInvitation

    invitation = RFQInvitation.query.filter_by(
        tenant_id=tenant_id, rfq_id=rfq_id, vendor_id=vendor_user.vendor_id
    ).first()
    if not invitation:
        raise APIError("Your organization was not invited to this RFQ", status=403)
    return invitation


def assert_vendor_owns_subcontract_certificate(tenant_id, *, vendor_user: VendorPortalUser, certificate_id):
    from app.modules.sub.models import PaymentCertificate, SubcontractAgreement

    certificate = PaymentCertificate.query.filter_by(id=certificate_id, tenant_id=tenant_id).first()
    if not certificate:
        raise APIError("Subcontract certificate not found", status=404)

    agreement = SubcontractAgreement.query.filter_by(id=certificate.agreement_id, tenant_id=tenant_id).first()
    if not agreement or agreement.subcontractor_id != vendor_user.vendor_id:
        raise APIError("This subcontract certificate does not belong to your organization", status=403)
    return certificate


# --- Order acknowledgment (VNP-01) ------------------------------------------------

def acknowledge_order(tenant_id, *, vendor_user: VendorPortalUser, purchase_order_id, expected_delivery_date=None):
    assert_vendor_owns_purchase_order(tenant_id, vendor_user=vendor_user, purchase_order_id=purchase_order_id)

    existing = OrderAcknowledgment.query.filter_by(purchase_order_id=purchase_order_id, tenant_id=tenant_id).first()
    if existing:
        raise APIError("This purchase order has already been acknowledged", status=409)

    ack = OrderAcknowledgment(
        tenant_id=tenant_id,
        vendor_user_id=vendor_user.id,
        purchase_order_id=purchase_order_id,
        acknowledged_at=datetime.now(timezone.utc),
        expected_delivery_date=expected_delivery_date,
    )
    db.session.add(ack)
    db.session.commit()
    return ack


# --- Quote submission (VNP-02) ---------------------------------------------------

def submit_quote_as_vendor(tenant_id, *, vendor_user: VendorPortalUser, rfq_id, price, lead_time_days=None, payment_terms=None):
    assert_vendor_invited_to_rfq(tenant_id, vendor_user=vendor_user, rfq_id=rfq_id)

    from app.modules.prc.models import RFQQuotation

    existing = RFQQuotation.query.filter_by(tenant_id=tenant_id, rfq_id=rfq_id, vendor_id=vendor_user.vendor_id).first()
    if existing:
        raise APIError("Your organization has already submitted a quote for this RFQ", status=409)

    quotation = RFQQuotation(
        tenant_id=tenant_id,
        rfq_id=rfq_id,
        vendor_id=vendor_user.vendor_id,
        price=price,
        lead_time_days=lead_time_days,
        payment_terms=payment_terms,
        submitted_at=datetime.now(timezone.utc),
    )
    db.session.add(quotation)
    db.session.commit()
    return quotation


# --- Invoice upload (VNP-03, VNP-04) ----------------------------------------------

def upload_vendor_invoice(
    tenant_id, *, vendor_user: VendorPortalUser, invoice_number, amount, purchase_order_id=None, subcontract_certificate_id=None, invoice_document_id=None
):
    if bool(purchase_order_id) == bool(subcontract_certificate_id):
        raise APIError("Exactly one of purchase_order_id or subcontract_certificate_id is required", status=400)

    if purchase_order_id:
        assert_vendor_owns_purchase_order(tenant_id, vendor_user=vendor_user, purchase_order_id=purchase_order_id)
    else:
        assert_vendor_owns_subcontract_certificate(tenant_id, vendor_user=vendor_user, certificate_id=subcontract_certificate_id)

    upload = VendorInvoiceUpload(
        tenant_id=tenant_id,
        vendor_user_id=vendor_user.id,
        purchase_order_id=purchase_order_id,
        subcontract_certificate_id=subcontract_certificate_id,
        invoice_document_id=invoice_document_id,
        invoice_number=invoice_number,
        amount=amount,
        uploaded_at=datetime.now(timezone.utc),
    )
    db.session.add(upload)
    db.session.commit()
    return upload


def get_vendor_invoice_uploads(tenant_id, *, vendor_user: VendorPortalUser):
    """VNP-04: every invoice this vendor has submitted, with its
    current status -- a vendor's own upload list is inherently
    self-scoped (filtered by vendor_user_id, which belongs to exactly
    one vendor), so no separate ownership check is needed here."""
    return VendorInvoiceUpload.query.filter_by(tenant_id=tenant_id, vendor_user_id=vendor_user.id).all()


# --- Banking detail change (VNP-05, business rule) --------------------------------

def submit_banking_change(tenant_id, *, vendor_user: VendorPortalUser, proposed_banking_details):
    """
    Creates a PENDING request only -- this function has no code path
    that touches Module 7's live Vendor.banking_details field. That
    field is only ever written by approve_banking_change, below.
    """
    request = VendorBankingChangeRequest(
        tenant_id=tenant_id,
        vendor_user_id=vendor_user.id,
        vendor_id=vendor_user.vendor_id,
        proposed_banking_details=proposed_banking_details,
        submitted_at=datetime.now(timezone.utc),
    )
    db.session.add(request)
    db.session.commit()
    return request


def approve_banking_change(request: VendorBankingChangeRequest, *, approved_by):
    """
    Business rule: THE only path that ever writes vendor-submitted
    banking details into Module 7's live Vendor record -- gated behind
    an internal Finance approval (the route calling this must require a
    distinct, internal-only permission, never one a vendor-portal
    session could hold).
    """
    if request.status != "pending":
        raise APIError("Banking change request has already been decided", status=409)

    from app.modules.prc.models import Vendor

    vendor = Vendor.query.filter_by(id=request.vendor_id, tenant_id=request.tenant_id).first()
    if not vendor:
        raise APIError("Vendor not found", status=404)

    vendor.banking_details = request.proposed_banking_details
    request.status = "approved"
    request.reviewed_by = approved_by
    request.reviewed_at = datetime.now(timezone.utc)
    db.session.commit()
    return request


def reject_banking_change(request: VendorBankingChangeRequest, *, reviewed_by, reason):
    if request.status != "pending":
        raise APIError("Banking change request has already been decided", status=409)
    if not reason:
        raise APIError("A reason is required to reject a banking change request", status=400)

    request.status = "rejected"
    request.reviewed_by = reviewed_by
    request.reviewed_at = datetime.now(timezone.utc)
    request.rejection_reason = reason
    db.session.commit()
    return request
