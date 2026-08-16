"""
Module 18 — Client Billing (Code: BIL)
SRS Section 4.18.

The revenue-recognition engine of the platform: converts verified
progress into certified, client-facing billing documents.

Key Data Entities (SRS 4.18): ProgressCertificate,
MilestoneBillingSchedule, RetentionLedger, VariationOrder, Claim,
PaymentTracking, OutstandingInvoice, RevenueRecognitionRecord.

Design notes:
  - `OutstandingInvoice` is not a stored table -- BIL-07 asks for a
    REPORT by client/project/age band, which is a computed view over
    PaymentTracking (services.get_outstanding_invoices_report), the
    same reasoning as every other computed-report entity in this
    codebase (WFM's labor cost allocation, FIN's project cost summary).
  - Business rule (SRS 4.18): a Variation Order not yet approved may be
    tracked as a pending value in reporting but must NOT appear in a
    Progress Certificate as billable -- enforced in
    services.add_certificate_line, which refuses to add a line
    referencing an unapproved VariationOrder.
  - Business rule (SRS 4.18, BIL-10): cumulative billed quantity per
    BOQ item is validated against contracted (plus approved variation)
    quantity before a certificate line can be added, preventing
    double-billing. `contracted_quantity` is caller-supplied (Module
    2/3 owns that figure); the approved-variation total and
    already-billed total are both computed from this module's own
    data, which it does own.
  - Business rule (SRS 4.18, BIL-08): percentage-of-completion revenue
    is calculated from the SAME progress data used for the Progress
    Certificate, and any divergence between billed and recognized
    revenue is tracked explicitly (`over_under_billing_position` on
    RevenueRecognitionRecord), never silently reconciled away.
"""
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin


CERTIFICATE_STATUSES = ("draft", "submitted", "client_approved", "rejected")
CLIENT_APPROVAL_METHODS = ("in_app", "manual_upload")
VARIATION_ORDER_STATUSES = ("pending", "approved", "rejected")
CLAIM_TYPES = ("delay_costs", "disruption", "unforeseen_conditions", "other")
CLAIM_STATUSES = ("submitted", "under_review", "approved", "rejected")
PAYMENT_STATUSES = ("submitted", "certified", "paid", "overdue")
REVENUE_METHODS = ("percentage_of_completion", "completed_contract")


class ProgressCertificate(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """BIL-01: generated from verified Work Completed quantities
    (Module 6) and/or measurement sheets, applying CBS contract rates.
    BIL-09: routes through a client-approval step before the associated
    receivable is recognized."""

    __tablename__ = "bil_progress_certificates"

    contract_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)  # ctm_contracts.id, loose reference
    project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)

    certificate_number = db.Column(db.String(128), nullable=False)
    period_start = db.Column(db.Date, nullable=True)
    period_end = db.Column(db.Date, nullable=True)

    gross_certified_amount = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    retention_withheld = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    net_payable = db.Column(db.Numeric(18, 4), nullable=False, default=0)

    status = db.Column(db.String(16), nullable=False, default="draft", index=True)
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    client_approval_method = db.Column(db.String(16), nullable=True)
    approved_by = db.Column(db.String(255), nullable=True)  # often an external client/consultant name
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)

    lines = relationship("ProgressCertificateLine", back_populates="certificate", cascade="all, delete-orphan")
    payment_tracking = relationship("PaymentTracking", back_populates="certificate", uselist=False)

    __table_args__ = (
        db.CheckConstraint(f"status IN {CERTIFICATE_STATUSES}", name="ck_bil_certificate_status"),
        db.UniqueConstraint("tenant_id", "certificate_number", name="uq_bil_certificate_tenant_number"),
    )


class ProgressCertificateLine(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """Business rules enforced at creation time (services.py): an
    unapproved VariationOrder cannot back a line, and cumulative
    billed quantity cannot exceed contracted + approved-variation
    quantity for the BOQ item (BIL-10)."""

    __tablename__ = "bil_progress_certificate_lines"

    certificate_id = db.Column(UUID(as_uuid=True), db.ForeignKey("bil_progress_certificates.id"), nullable=False, index=True)
    boq_item_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)  # loose reference
    variation_order_id = db.Column(UUID(as_uuid=True), db.ForeignKey("bil_variation_orders.id"), nullable=True)

    certified_quantity = db.Column(db.Numeric(18, 4), nullable=False)
    rate = db.Column(db.Numeric(18, 4), nullable=False)
    amount = db.Column(db.Numeric(18, 4), nullable=False)

    certificate = relationship("ProgressCertificate", back_populates="lines")


class MilestoneBillingSchedule(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """BIL-02: for contracts billed against defined milestones rather
    than measured quantities."""

    __tablename__ = "bil_milestone_schedules"

    contract_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    milestone_name = db.Column(db.String(255), nullable=False)
    milestone_amount = db.Column(db.Numeric(18, 4), nullable=False)
    sequence_order = db.Column(db.Integer, nullable=False, default=1)

    achieved = db.Column(db.Boolean, nullable=False, default=False)
    achieved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    billed = db.Column(db.Boolean, nullable=False, default=False)
    certificate_id = db.Column(UUID(as_uuid=True), db.ForeignKey("bil_progress_certificates.id"), nullable=True)


class RetentionLedger(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """BIL-03: retention withheld per certificate, tracked cumulatively
    per contract, with scheduled release referencing Module 4's
    contract terms (loose reference)."""

    __tablename__ = "bil_retention_ledgers"

    contract_id = db.Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    percentage = db.Column(db.Numeric(5, 2), nullable=False, default=5)
    amount_withheld = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    released_amount = db.Column(db.Numeric(18, 4), nullable=False, default=0)


class VariationOrder(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """BIL-04: at BOQ-item level, requiring client/consultant approval
    before the varied quantity/rate is billable. Business rule: not-yet
    -approved orders can be reported on as pending value but never
    appear in a Progress Certificate as billable -- enforced by
    services.add_certificate_line refusing to reference anything but
    an approved order."""

    __tablename__ = "bil_variation_orders"

    contract_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    boq_item_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)  # loose reference; null if a new item

    description = db.Column(db.Text, nullable=False)
    varied_quantity = db.Column(db.Numeric(18, 4), nullable=True)
    varied_rate = db.Column(db.Numeric(18, 4), nullable=True)
    status = db.Column(db.String(16), nullable=False, default="pending")

    submitted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    approved_by = db.Column(db.String(255), nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (db.CheckConstraint(f"status IN {VARIATION_ORDER_STATUSES}", name="ck_bil_vo_status"),)


class Claim(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """BIL-05: delay costs, disruption, unforeseen conditions, with a
    supporting documentation package."""

    __tablename__ = "bil_claims"

    contract_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    claim_type = db.Column(db.String(24), nullable=False)
    description = db.Column(db.Text, nullable=False)
    claimed_amount = db.Column(db.Numeric(18, 4), nullable=True)
    supporting_document_ids = db.Column(JSONB, nullable=True)  # list of documents.id, as strings
    status = db.Column(db.String(16), nullable=False, default="submitted")
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    reviewed_by = db.Column(db.String(255), nullable=True)
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        db.CheckConstraint(f"claim_type IN {CLAIM_TYPES}", name="ck_bil_claim_type"),
        db.CheckConstraint(f"status IN {CLAIM_STATUSES}", name="ck_bil_claim_status"),
    )


class PaymentTracking(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """BIL-06: per-certificate payment lifecycle (submitted → certified
    → paid, or overdue), distinct from the certificate's own
    draft/submitted/approved workflow -- this tracks the INVOICE once
    it exists, not the approval of the certificate that created it."""

    __tablename__ = "bil_payment_tracking"

    certificate_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("bil_progress_certificates.id"), nullable=False, unique=True, index=True
    )
    status = db.Column(db.String(16), nullable=False, default="submitted", index=True)
    due_date = db.Column(db.Date, nullable=True)
    paid_at = db.Column(db.DateTime(timezone=True), nullable=True)
    paid_amount = db.Column(db.Numeric(18, 4), nullable=True)

    certificate = relationship("ProgressCertificate", back_populates="payment_tracking")

    __table_args__ = (db.CheckConstraint(f"status IN {PAYMENT_STATUSES}", name="ck_bil_payment_status"),)


class RevenueRecognitionRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """BIL-08: business rule -- computed from the same progress data
    used for Progress Certificates; the over/under-billing position is
    tracked explicitly, never silently reconciled. Stored (not purely
    computed-on-read) because a recognition record feeds Module 17's
    financial statements and is itself a referenceable accounting
    record, not just a display figure."""

    __tablename__ = "bil_revenue_recognition_records"

    contract_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)

    method = db.Column(db.String(24), nullable=False, default="percentage_of_completion")
    percentage_complete = db.Column(db.Numeric(5, 2), nullable=True)
    cumulative_revenue_recognized = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    cumulative_billed = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    over_under_billing_position = db.Column(db.Numeric(18, 4), nullable=False, default=0)  # positive = over-billed

    generated_at = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (db.CheckConstraint(f"method IN {REVENUE_METHODS}", name="ck_bil_revenue_method"),)
