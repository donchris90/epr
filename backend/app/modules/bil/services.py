"""
Module 18 — Client Billing (Code: BIL)
Service layer — business logic other modules must call through rather
than querying bil_* tables directly (SRS Section 3.3).

Business rules encoded here (SRS 4.18):
  - A Variation Order not yet approved may be tracked as a pending
    value in reporting but must not appear in a Progress Certificate
    as billable.
  - Cumulative billed quantity per BOQ item is validated against
    contracted (plus approved variation) quantity, preventing
    double-billing (BIL-10).
  - Percentage-of-completion revenue is calculated from the same
    progress data used for the Progress Certificate, with any
    divergence between billed and recognized revenue tracked
    explicitly, never silently reconciled.
"""
from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.utils.errors import APIError
from app.modules.bil.models import (
    ProgressCertificate,
    ProgressCertificateLine,
    VariationOrder,
    PaymentTracking,
    RevenueRecognitionRecord,
)


# --- Certificate lines (BIL-04, BIL-10, business rules) -----------------------

def get_approved_variation_quantity(tenant_id, *, boq_item_id) -> Decimal:
    """Sum of varied_quantity across APPROVED variation orders for this
    BOQ item -- computed from this module's own data."""
    total = (
        db.session.query(db.func.coalesce(db.func.sum(VariationOrder.varied_quantity), 0))
        .filter(
            VariationOrder.tenant_id == tenant_id,
            VariationOrder.boq_item_id == boq_item_id,
            VariationOrder.status == "approved",
        )
        .scalar()
    )
    return Decimal(total)


def get_cumulative_billed_quantity(tenant_id, *, boq_item_id) -> Decimal:
    """Sum of certified_quantity across all lines on non-rejected
    certificates (draft counts too -- a draft still represents intended
    billing that would double-count if not included; only a rejected
    certificate's lines are excluded)."""
    total = (
        db.session.query(db.func.coalesce(db.func.sum(ProgressCertificateLine.certified_quantity), 0))
        .join(ProgressCertificate, ProgressCertificateLine.certificate_id == ProgressCertificate.id)
        .filter(
            ProgressCertificateLine.tenant_id == tenant_id,
            ProgressCertificateLine.boq_item_id == boq_item_id,
            ProgressCertificate.status != "rejected",
        )
        .scalar()
    )
    return Decimal(total)


def add_certificate_line(
    tenant_id,
    *,
    certificate: ProgressCertificate,
    boq_item_id,
    certified_quantity,
    rate,
    contracted_quantity,
    variation_order_id=None,
):
    """
    Business rules enforced here:
      1. A line referencing a VariationOrder requires that order to be
         APPROVED -- a pending or rejected one cannot back a billable
         line, regardless of what quantity/rate it proposes.
      2. Cumulative billed quantity (existing + this line) cannot
         exceed contracted_quantity + approved variation quantity for
         this BOQ item (BIL-10) -- `contracted_quantity` is supplied by
         the caller since Module 2/3 owns that figure.
    """
    if certificate.status not in ("draft",):
        raise APIError("Cannot add lines to a certificate that is not in draft", status=409)

    if variation_order_id:
        vo = VariationOrder.query.filter_by(id=variation_order_id, tenant_id=tenant_id).first()
        if not vo:
            raise APIError("Variation order not found", status=404)
        if vo.status != "approved":
            raise APIError(
                "Cannot bill against an unapproved Variation Order",
                status=409,
                detail=f"Variation order status is '{vo.status}'; only an approved order is billable.",
            )

    certified_quantity = Decimal(str(certified_quantity))
    rate = Decimal(str(rate))
    contracted_quantity = Decimal(str(contracted_quantity))

    already_billed = get_cumulative_billed_quantity(tenant_id, boq_item_id=boq_item_id)
    approved_variation = get_approved_variation_quantity(tenant_id, boq_item_id=boq_item_id)
    allowed_total = contracted_quantity + approved_variation
    new_total = already_billed + certified_quantity

    if new_total > allowed_total:
        raise APIError(
            "Cumulative billed quantity would exceed contracted (plus approved variation) quantity",
            status=409,
            detail=f"Already billed {already_billed}, contracted+variation allows {allowed_total}, this line would bring total to {new_total}.",
        )

    line = ProgressCertificateLine(
        tenant_id=tenant_id,
        certificate_id=certificate.id,
        boq_item_id=boq_item_id,
        variation_order_id=variation_order_id,
        certified_quantity=certified_quantity,
        rate=rate,
        amount=certified_quantity * rate,
    )
    db.session.add(line)

    certificate.gross_certified_amount = sum((l.amount for l in certificate.lines), Decimal("0"))
    db.session.commit()
    return line


# --- Certificate workflow (BIL-01, BIL-09) -------------------------------------

def apply_retention(certificate: ProgressCertificate, *, percentage):
    percentage = Decimal(str(percentage))
    certificate.retention_withheld = certificate.gross_certified_amount * percentage / Decimal("100")
    certificate.net_payable = certificate.gross_certified_amount - certificate.retention_withheld
    db.session.commit()
    return certificate


def submit_certificate(certificate: ProgressCertificate):
    if certificate.status != "draft":
        raise APIError("Only a draft certificate can be submitted", status=409)
    if not certificate.lines:
        raise APIError("Cannot submit an empty certificate", status=400)

    certificate.status = "submitted"
    certificate.submitted_at = datetime.now(timezone.utc)
    db.session.commit()

    # BIL-06: a submitted certificate immediately begins payment tracking.
    tracking = PaymentTracking(tenant_id=certificate.tenant_id, certificate_id=certificate.id, status="submitted")
    db.session.add(tracking)
    db.session.commit()
    return certificate


def approve_certificate(certificate: ProgressCertificate, *, approval_method, approved_by):
    """
    BIL-09: the client-approval step -- the associated receivable
    (Module 17's AR invoice) should only be recognized after this,
    which is why this function does not itself call
    app.modules.fin.services; the caller wiring the two modules
    together does that once approval succeeds, the same pattern used
    for EQP/WFM's certification lookup.
    """
    if certificate.status != "submitted":
        raise APIError("Only a submitted certificate can be approved", status=409)

    certificate.status = "client_approved"
    certificate.client_approval_method = approval_method
    certificate.approved_by = approved_by
    certificate.approved_at = datetime.now(timezone.utc)
    db.session.commit()

    if certificate.payment_tracking:
        certificate.payment_tracking.status = "certified"
        db.session.commit()

    return certificate


# --- Payment tracking & aging (BIL-06, BIL-07) ---------------------------------

def record_payment(tracking: PaymentTracking, *, paid_amount, paid_at=None):
    if tracking.status == "paid":
        raise APIError("Payment already recorded for this certificate", status=409)

    tracking.status = "paid"
    tracking.paid_amount = Decimal(str(paid_amount))
    tracking.paid_at = paid_at or datetime.now(timezone.utc)
    db.session.commit()
    return tracking


def refresh_overdue_status(tenant_id, *, as_of=None):
    """Flips submitted/certified tracking rows past their due date to
    'overdue' -- intended for a scheduled task, exposed as a plain
    function so it's callable on demand too."""
    from datetime import date

    as_of = as_of or date.today()
    overdue = PaymentTracking.query.filter(
        PaymentTracking.tenant_id == tenant_id,
        PaymentTracking.status.in_(("submitted", "certified")),
        PaymentTracking.due_date.isnot(None),
        PaymentTracking.due_date < as_of,
    ).all()

    for tracking in overdue:
        tracking.status = "overdue"

    db.session.commit()
    return overdue


def get_outstanding_invoices_report(tenant_id, *, as_of=None):
    """BIL-07: computed report by age band -- no stored table, same
    reasoning as every other computed-report function in this
    codebase."""
    from datetime import date

    as_of = as_of or date.today()
    outstanding = PaymentTracking.query.filter(
        PaymentTracking.tenant_id == tenant_id, PaymentTracking.status != "paid"
    ).all()

    bands = {"current": [], "1_30_days": [], "31_60_days": [], "61_90_days": [], "over_90_days": []}
    for tracking in outstanding:
        cert = tracking.certificate
        age_days = (as_of - tracking.due_date).days if tracking.due_date else 0
        if age_days <= 0:
            band = "current"
        elif age_days <= 30:
            band = "1_30_days"
        elif age_days <= 60:
            band = "31_60_days"
        elif age_days <= 90:
            band = "61_90_days"
        else:
            band = "over_90_days"

        bands[band].append(
            {
                "certificate_id": str(cert.id),
                "certificate_number": cert.certificate_number,
                "amount": str(cert.net_payable),
                "due_date": tracking.due_date.isoformat() if tracking.due_date else None,
                "status": tracking.status,
            }
        )

    return bands


# --- Revenue recognition (BIL-08, business rule) -------------------------------

def recognize_revenue(
    tenant_id, *, contract_id, period_start, period_end, contract_total_value, percentage_complete=None, method="percentage_of_completion"
):
    """
    Business rule: uses the SAME progress data (percentage_complete)
    the caller would have used to generate the Progress Certificate --
    this function does not independently guess or re-derive progress.
    `cumulative_billed` is computed from THIS module's own certificates
    (real, non-rejected ones), so any gap between billed and recognized
    is a genuine, trackable position, not a rounding artifact.
    """
    contract_total_value = Decimal(str(contract_total_value))

    if method == "percentage_of_completion":
        if percentage_complete is None:
            raise APIError("percentage_complete is required for the percentage-of-completion method", status=400)
        percentage_complete = Decimal(str(percentage_complete))
        cumulative_recognized = contract_total_value * percentage_complete / Decimal("100")
    else:  # completed_contract -- nothing recognized until completion
        cumulative_recognized = Decimal("0")

    cumulative_billed = (
        db.session.query(db.func.coalesce(db.func.sum(ProgressCertificate.gross_certified_amount), 0))
        .filter(
            ProgressCertificate.tenant_id == tenant_id,
            ProgressCertificate.contract_id == contract_id,
            ProgressCertificate.status.in_(("submitted", "client_approved")),
        )
        .scalar()
    )
    cumulative_billed = Decimal(cumulative_billed)

    over_under = cumulative_billed - cumulative_recognized

    record = RevenueRecognitionRecord(
        tenant_id=tenant_id,
        contract_id=contract_id,
        period_start=period_start,
        period_end=period_end,
        method=method,
        percentage_complete=percentage_complete,
        cumulative_revenue_recognized=cumulative_recognized,
        cumulative_billed=cumulative_billed,
        over_under_billing_position=over_under,
        generated_at=datetime.now(timezone.utc),
    )
    db.session.add(record)
    db.session.commit()
    return record
