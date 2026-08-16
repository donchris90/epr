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

from app.extensions import db
from app.utils.errors import APIError
from app.modules.scp.models import SubcontractorPortalUser


# --- Defense-in-depth ownership checks ------------------------------------------

def assert_subcontractor_owns_agreement(tenant_id, *, portal_user: SubcontractorPortalUser, agreement_id):
    from app.modules.sub.models import SubcontractAgreement

    agreement = SubcontractAgreement.query.filter_by(id=agreement_id, tenant_id=tenant_id).first()
    if not agreement or agreement.subcontractor_id != portal_user.subcontractor_id:
        raise APIError("This agreement does not belong to your organization", status=403)
    return agreement


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
