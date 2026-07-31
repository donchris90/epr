"""
Module 12 — Subcontractor Management (Code: SUB)
Service layer — business logic other modules must call through rather
than querying sub_* tables directly (SRS Section 3.3).

Business rules encoded here (SRS 4.12):
  - A subcontract Payment Certificate cannot be issued without a
    corresponding VERIFIED Measurement Sheet for the certified
    quantities.
  - Subcontract Retention release is a distinct approval step from
    main-contract retention release and never happens automatically
    from a main-contract event (enforced by this module simply never
    calling into Module 4's retention release, in either direction).
  - A new payment certification is blocked if the subcontractor has an
    expired compliance document, absent an explicit waiver (same
    pattern as PRC's vendor compliance gate on PO issuance).
"""
from datetime import date, datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.utils.errors import APIError
from app.modules.sub.models import (
    MeasurementSheet,
    PaymentCertificate,
    PaymentCertificateLine,
    BackCharge,
    SubcontractRetention,
    SubcontractClaim,
    PerformanceRating,
    ComplianceDocument,
    SubcontractScopeItem,
)


# --- Measurement sheets (SUB-04) ---------------------------------------------

def verify_measurement_sheet(sheet: MeasurementSheet, *, measured_by):
    if sheet.status == "verified":
        raise APIError("Measurement sheet is already verified", status=409)

    sheet.status = "verified"
    sheet.measured_by = measured_by
    sheet.measured_at = datetime.now(timezone.utc)
    db.session.commit()
    return sheet


# --- Payment certificates (SUB-05, business rules) ---------------------------

def issue_payment_certificate(
    tenant_id,
    *,
    agreement,
    certificate_number,
    measurement_sheet_ids: list,
    period_start=None,
    period_end=None,
    back_charge_ids=None,
    waiver=False,
    waiver_reason=None,
    waiver_by=None,
    as_of=None,
):
    """
    Business rule: every certified line must reference a VERIFIED
    Measurement Sheet -- not merely an existing one. Also gated by
    subcontractor compliance document expiry (SUB-09), same pattern as
    PRC's vendor compliance check.
    """
    if not measurement_sheet_ids:
        raise APIError("At least one verified measurement sheet is required to issue a certificate", status=400)

    sheets = MeasurementSheet.query.filter(
        MeasurementSheet.id.in_(measurement_sheet_ids), MeasurementSheet.tenant_id == tenant_id
    ).all()
    if len(sheets) != len(measurement_sheet_ids):
        raise APIError("One or more measurement sheets not found", status=404)

    unverified = [s for s in sheets if s.status != "verified"]
    if unverified:
        raise APIError(
            "Cannot certify against unverified measurement sheets",
            status=409,
            detail=f"{len(unverified)} sheet(s) are not yet verified.",
        )

    # Compliance gate (SUB-09).
    as_of = as_of or date.today()
    expired_docs = ComplianceDocument.query.filter(
        ComplianceDocument.subcontractor_id == agreement.subcontractor_id,
        ComplianceDocument.valid_until.isnot(None),
        ComplianceDocument.valid_until < as_of,
    ).all()
    if expired_docs and not waiver:
        raise APIError(
            "Subcontractor has expired compliance documents",
            status=409,
            detail=f"Expired: {', '.join(d.doc_type for d in expired_docs)}. Issue with a waiver to override.",
        )

    certificate = PaymentCertificate(
        tenant_id=tenant_id,
        agreement_id=agreement.id,
        certificate_number=certificate_number,
        period_start=period_start,
        period_end=period_end,
        compliance_waiver=bool(expired_docs and waiver),
        compliance_waiver_reason=waiver_reason if expired_docs else None,
        compliance_waiver_by=waiver_by if expired_docs else None,
    )
    db.session.add(certificate)
    db.session.flush()

    gross = Decimal("0")
    for sheet in sheets:
        scope = SubcontractScopeItem.query.get(sheet.scope_item_id)
        rate = scope.rate if scope and scope.rate is not None else Decimal("0")
        amount = sheet.verified_quantity * rate
        gross += amount

        db.session.add(
            PaymentCertificateLine(
                tenant_id=tenant_id,
                certificate_id=certificate.id,
                measurement_sheet_id=sheet.id,
                certified_quantity=sheet.verified_quantity,
                rate=rate,
                amount=amount,
            )
        )

    retention_pct = agreement.retention.percentage if agreement.retention else agreement.retention_percentage
    retention_amount = gross * retention_pct / Decimal("100")

    back_charges_total = Decimal("0")
    if back_charge_ids:
        charges = BackCharge.query.filter(
            BackCharge.id.in_(back_charge_ids), BackCharge.tenant_id == tenant_id, BackCharge.payment_certificate_id.is_(None)
        ).all()
        for charge in charges:
            charge.payment_certificate_id = certificate.id
            back_charges_total += charge.amount

    certificate.gross_certified_amount = gross
    certificate.retention_withheld = retention_amount
    certificate.back_charges_total = back_charges_total
    certificate.net_payable = gross - retention_amount - back_charges_total
    certificate.status = "issued"
    certificate.issued_at = datetime.now(timezone.utc)

    if agreement.retention:
        agreement.retention.amount_withheld += retention_amount

    db.session.commit()
    return certificate


# --- Subcontract retention (SUB-06, business rule) ----------------------------

def release_subcontract_retention(retention: SubcontractRetention, *, stage: str, actor_id=None):
    """
    Business rule: a distinct approval step, independent of Module 4's
    main-contract retention release -- see module docstring for why
    there is deliberately no code path connecting the two.
    """
    if stage == "substantial_completion":
        if retention.released_substantial_completion:
            raise APIError("Substantial completion retention already released", status=409)
        retention.released_substantial_completion = True
    elif stage == "final":
        if not retention.released_substantial_completion:
            raise APIError("Cannot release final retention before substantial completion retention", status=409)
        if retention.released_final:
            raise APIError("Final retention already released", status=409)
        retention.released_final = True
    else:
        raise APIError("Invalid release stage", status=400)

    db.session.commit()
    return retention


# --- Claims (SUB-07) -----------------------------------------------------------

def review_claim(claim: SubcontractClaim, *, decision: str, reviewed_by, response_notes=None):
    if claim.status not in ("submitted", "under_review"):
        raise APIError("Claim has already been decided", status=409)
    if decision not in ("approved", "rejected", "under_review"):
        raise APIError("Invalid decision", status=400)

    claim.status = decision
    claim.reviewed_by = reviewed_by
    claim.reviewed_at = datetime.now(timezone.utc)
    claim.response_notes = response_notes
    db.session.commit()
    return claim


# --- Performance ratings (SUB-08) -----------------------------------------------

def add_performance_rating(
    tenant_id, *, subcontractor_id, quality_score, schedule_score, safety_score, responsiveness_score, rated_by, project_id=None, period_label=None
):
    scores = [Decimal(str(s)) for s in (quality_score, schedule_score, safety_score, responsiveness_score)]
    overall = sum(scores) / Decimal("4")

    rating = PerformanceRating(
        tenant_id=tenant_id,
        subcontractor_id=subcontractor_id,
        project_id=project_id,
        period_label=period_label,
        quality_score=scores[0],
        schedule_score=scores[1],
        safety_score=scores[2],
        responsiveness_score=scores[3],
        overall_score=overall,
        rated_by=rated_by,
        rated_at=datetime.now(timezone.utc),
    )
    db.session.add(rating)
    db.session.commit()
    return rating
