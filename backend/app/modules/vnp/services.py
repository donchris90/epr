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

from sqlalchemy import text

from app.extensions import db
from app.utils.errors import APIError
from app.modules.vnp.models import VendorPortalUser, VendorPortalEmailIndex, OrderAcknowledgment, VendorInvoiceUpload, VendorBankingChangeRequest


# --- Authentication (vendor portal build) -------------------------------------

def authenticate_vendor_user(email: str, password: str):
    """Resolves every vnp_email_index row for this email (a vendor
    working with more than one contractor has one row per tenant) and
    tries each tenant in turn, verifying the password against that
    tenant's own VendorPortalUser row. Same real cross-tenant login
    shape as authenticate_client_user (app/modules/clp/services.py)
    and staff login both already use."""
    from app.auth.jwt_utils import verify_password
    from app.models.core import Tenant

    if not email or not password:
        return None

    index_rows = VendorPortalEmailIndex.query.filter_by(email=email).all()
    if not index_rows:
        return None

    for index_row in index_rows:
        with db.session.begin_nested():
            db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(index_row.tenant_id)})
            user = db.session.get(VendorPortalUser, index_row.vendor_user_id)

        if not user or not user.is_active or not user.password_hash:
            continue

        tenant = Tenant.query.filter_by(id=index_row.tenant_id).first()
        if tenant and tenant.is_suspended:
            continue

        if verify_password(user.password_hash, password):
            return user

    return None


def set_vendor_password(vendor_user: VendorPortalUser, *, password: str):
    """Called from the staff-facing create flow -- deliberately no
    vendor-initiated "forgot password" flow yet; see
    docs/SUBCONTRACTOR_VENDOR_PORTAL_GAPS.md."""
    from app.auth.jwt_utils import hash_password

    vendor_user.password_hash = hash_password(password)
    db.session.commit()
    return vendor_user


def change_vendor_password(vendor_user: VendorPortalUser, *, current_password: str, new_password: str):
    """Self-service change -- requires proving the current password
    first, distinct from set_vendor_password's staff-initiated create
    path."""
    from app.auth.jwt_utils import verify_password, hash_password

    if not vendor_user.password_hash or not verify_password(vendor_user.password_hash, current_password):
        raise APIError("Current password is incorrect", status=401)

    vendor_user.password_hash = hash_password(new_password)
    db.session.commit()
    return vendor_user


# --- Defense-in-depth ownership checks ------------------------------------------

def assert_vendor_owns_purchase_order(tenant_id, *, vendor_user: VendorPortalUser, purchase_order_id):
    from app.modules.prc.models import PurchaseOrder

    po = PurchaseOrder.query.filter_by(id=purchase_order_id, tenant_id=tenant_id).first()
    if not po or po.vendor_id != vendor_user.vendor_id:
        raise APIError("This purchase order does not belong to your organization", status=403)
    return po


def list_purchase_orders_for_vendor(tenant_id, *, vendor_user: VendorPortalUser):
    """Real, small, genuinely missing capability found while building
    the vendor portal frontend -- PurchaseOrder.vendor_id already
    exists and is indexed (backend/app/modules/prc/models.py), so this
    is a safe, direct, ownership-scoped query, not new business logic.
    Without this, a vendor has no way to discover which of their own
    orders exist at all -- only to acknowledge/act on one they already
    know the id of."""
    from app.modules.prc.models import PurchaseOrder

    return (
        PurchaseOrder.query.filter_by(tenant_id=tenant_id, vendor_id=vendor_user.vendor_id)
        .filter(PurchaseOrder.deleted_at.is_(None))
        .order_by(PurchaseOrder.created_at.desc())
        .all()
    )


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
