"""
Module 27 — Subcontractor Portal (Code: SCP)
Service layer — business logic other modules must call through rather
than querying scp_* tables directly (SRS Section 3.3 convention).

Every function here enforces subcontractor-ownership as an
unconditional first check (assert_subcontractor_owns_agreement /
assert_subcontractor_owns_certificate), independent of the caller's
permission grant -- the same defense-in-depth pattern as Module 22's
client-scope check and Module 23's vendor-ownership check. A
subcontractor-portal session holding a (misconfigured) broad `scp:*`
grant still can't reach another subcontractor's agreement, because
this check doesn't consult the permission system at all -- it
consults SubcontractAgreement.subcontractor_id directly.
"""
from datetime import datetime, timezone

from sqlalchemy import text

from app.extensions import db
from app.utils.errors import APIError
from app.modules.scp.models import SubcontractorPortalUser, SubcontractorPortalEmailIndex


# --- Authentication (subcontractor portal build) ----------------------------------

def authenticate_subcontractor_user(email: str, password: str):
    """Resolves every scp_email_index row for this email (a
    subcontractor working with more than one contractor has one row
    per tenant) and tries each tenant in turn, verifying the password
    against that tenant's own SubcontractorPortalUser row. Same real
    cross-tenant login shape as authenticate_client_user
    (app/modules/clp/services.py) and staff login both already use."""
    from app.auth.jwt_utils import verify_password
    from app.models.core import Tenant

    if not email or not password:
        return None

    index_rows = SubcontractorPortalEmailIndex.query.filter_by(email=email).all()
    if not index_rows:
        return None

    for index_row in index_rows:
        with db.session.begin_nested():
            db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(index_row.tenant_id)})
            user = db.session.get(SubcontractorPortalUser, index_row.portal_user_id)

        if not user or not user.is_active or not user.password_hash:
            continue

        tenant = Tenant.query.filter_by(id=index_row.tenant_id).first()
        if tenant and tenant.is_suspended:
            continue

        if verify_password(user.password_hash, password):
            return user

    return None


def set_subcontractor_password(portal_user: SubcontractorPortalUser, *, password: str):
    """Called from the staff-facing create flow -- deliberately no
    subcontractor-initiated "forgot password" flow yet; see
    docs/SUBCONTRACTOR_VENDOR_PORTAL_GAPS.md."""
    from app.auth.jwt_utils import hash_password

    portal_user.password_hash = hash_password(password)
    db.session.commit()
    return portal_user


def change_subcontractor_password(portal_user: SubcontractorPortalUser, *, current_password: str, new_password: str):
    """Self-service change -- requires proving the current password
    first, distinct from set_subcontractor_password's staff-initiated
    create path."""
    from app.auth.jwt_utils import verify_password, hash_password

    if not portal_user.password_hash or not verify_password(portal_user.password_hash, current_password):
        raise APIError("Current password is incorrect", status=401)

    portal_user.password_hash = hash_password(new_password)
    db.session.commit()
    return portal_user


# --- Defense-in-depth ownership checks ------------------------------------------

def assert_subcontractor_owns_agreement(tenant_id, *, portal_user: SubcontractorPortalUser, agreement_id):
    from app.modules.sub.models import SubcontractAgreement

    agreement = SubcontractAgreement.query.filter_by(id=agreement_id, tenant_id=tenant_id).first()
    if not agreement or agreement.subcontractor_id != portal_user.subcontractor_id:
        raise APIError("This agreement does not belong to your organization", status=403)
    return agreement


def list_agreements_for_subcontractor(tenant_id, *, portal_user: SubcontractorPortalUser):
    """Real, small, genuinely missing capability found while building
    the subcontractor portal frontend -- the existing GET
    /v1/sub/agreements (app/modules/sub/routes.py) is staff-only
    (sub:read) and tenant-wide with no subcontractor_id filter at all,
    so it's both unreachable by a real portal session and would leak
    every subcontractor's agreements if it somehow were. This is a
    safe, direct, ownership-scoped query instead -- the same real
    reasoning as VNP's list_purchase_orders_for_vendor."""
    from app.modules.sub.models import SubcontractAgreement

    return (
        SubcontractAgreement.query.filter_by(tenant_id=tenant_id, subcontractor_id=portal_user.subcontractor_id)
        .order_by(SubcontractAgreement.created_at.desc())
        .all()
    )


def assert_subcontractor_owns_certificate(tenant_id, *, portal_user: SubcontractorPortalUser, certificate_id):
    from app.modules.sub.models import PaymentCertificate, SubcontractAgreement

    certificate = PaymentCertificate.query.filter_by(id=certificate_id, tenant_id=tenant_id).first()
    if not certificate:
        raise APIError("Payment certificate not found", status=404)

    agreement = SubcontractAgreement.query.filter_by(id=certificate.agreement_id, tenant_id=tenant_id).first()
    if not agreement or agreement.subcontractor_id != portal_user.subcontractor_id:
        raise APIError("This payment certificate does not belong to your organization", status=403)
    return certificate


# --- Progress submission (SUB-03, portal-facing half) ---------------------------

def submit_progress_as_subcontractor(
    tenant_id, *, portal_user: SubcontractorPortalUser, agreement_id, submitted_quantity, scope_item_id=None
):
    assert_subcontractor_owns_agreement(tenant_id, portal_user=portal_user, agreement_id=agreement_id)

    from app.modules.sub.models import SubcontractProgressEntry

    entry = SubcontractProgressEntry(
        tenant_id=tenant_id,
        agreement_id=agreement_id,
        scope_item_id=scope_item_id,
        submitted_quantity=submitted_quantity,
        submitted_at=datetime.now(timezone.utc),
        submitted_by=portal_user.id,
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def get_progress_entries_for_subcontractor(tenant_id, *, portal_user: SubcontractorPortalUser, agreement_id):
    assert_subcontractor_owns_agreement(tenant_id, portal_user=portal_user, agreement_id=agreement_id)

    from app.modules.sub.models import SubcontractProgressEntry

    return SubcontractProgressEntry.query.filter_by(tenant_id=tenant_id, agreement_id=agreement_id).all()


# --- Payment certificate visibility (SUB-05/06, read-only) ----------------------

def get_payment_certificates_for_subcontractor(tenant_id, *, portal_user: SubcontractorPortalUser, agreement_id):
    assert_subcontractor_owns_agreement(tenant_id, portal_user=portal_user, agreement_id=agreement_id)

    from app.modules.sub.models import PaymentCertificate

    return PaymentCertificate.query.filter_by(tenant_id=tenant_id, agreement_id=agreement_id).all()


# --- Claim submission (SUB-07) ---------------------------------------------------

def submit_claim_as_subcontractor(
    tenant_id, *, portal_user: SubcontractorPortalUser, agreement_id, claim_type, description,
    claimed_amount=None, claimed_days=None
):
    assert_subcontractor_owns_agreement(tenant_id, portal_user=portal_user, agreement_id=agreement_id)

    from app.modules.sub.models import SubcontractClaim

    claim = SubcontractClaim(
        tenant_id=tenant_id,
        agreement_id=agreement_id,
        claim_type=claim_type,
        description=description,
        claimed_amount=claimed_amount,
        claimed_days=claimed_days,
        status="submitted",
        submitted_at=datetime.now(timezone.utc),
    )
    db.session.add(claim)
    db.session.commit()
    return claim


def get_claims_for_subcontractor(tenant_id, *, portal_user: SubcontractorPortalUser, agreement_id):
    assert_subcontractor_owns_agreement(tenant_id, portal_user=portal_user, agreement_id=agreement_id)

    from app.modules.sub.models import SubcontractClaim

    return SubcontractClaim.query.filter_by(tenant_id=tenant_id, agreement_id=agreement_id).all()
