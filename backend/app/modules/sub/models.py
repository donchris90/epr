"""
Module 12 — Subcontractor Management (Code: SUB)
SRS Section 4.12.

Manages the subcontractor as a quasi-client-and-vendor hybrid: a
commercial relationship shaped like Module 4's Contract (agreement,
retention, payment certificates) but running the OTHER direction --
the company pays the subcontractor for verified work, rather than being
paid.

Key Data Entities (SRS 4.12): SubcontractAgreement, SubcontractScopeItem,
SubcontractProgressEntry, MeasurementSheet, PaymentCertificate
(subcontract), SubcontractRetention, SubcontractClaim, PerformanceRating,
ComplianceDocument.

Design notes:
  - `Subcontractor` (the company itself) is not in the SRS's named
    entity list but is the necessary anchor for agreements, ratings,
    and compliance documents -- the same kind of addition already made
    for INV's MaterialItem and PRC's Vendor. Deliberately a SEPARATE
    entity from PRC's Vendor (not reused), since a subcontractor's data
    needs (performance ratings, safety/labor compliance, agreement
    structure) differ enough from a materials/services vendor's that
    conflating them would be wrong, not just untidy.
  - `PaymentCertificateLine` links each certified line item back to the
    specific MeasurementSheet it was verified against -- this FK is
    what makes the first business rule enforceable at the data layer,
    not just in application logic.
  - Business rule (SRS 4.12): a Payment Certificate cannot be issued
    without a corresponding VERIFIED Measurement Sheet for the
    certified quantities -- enforced in services.issue_payment_certificate.
  - Business rule (SRS 4.12): Subcontract Retention release is a
    distinct approval step, never automatic from a main-contract event.
    This module does not call into app.modules.ctm's retention release
    at all, in either direction -- the independence is enforced by
    simply not writing that integration, which is the surest way to
    guarantee "does not occur automatically."
"""
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin


SUBCONTRACTOR_STATUSES = ("active", "inactive")
AGREEMENT_STATUSES = ("active", "completed", "terminated")
PROGRESS_STATUSES = ("submitted", "verified", "rejected")
MEASUREMENT_SHEET_STATUSES = ("draft", "verified")
CERTIFICATE_STATUSES = ("draft", "issued")
BACK_CHARGE_CATEGORIES = ("rework", "materials_supplied", "other")
CLAIM_TYPES = ("delay", "additional_scope", "other")
CLAIM_STATUSES = ("submitted", "under_review", "approved", "rejected")
COMPLIANCE_DOC_TYPES = ("insurance", "safety_certification", "tax_clearance", "labor_law_compliance")


class Subcontractor(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """The subcontracting company -- see module docstring for why this
    is a distinct entity from PRC's Vendor."""

    __tablename__ = "sub_subcontractors"

    name = db.Column(db.String(255), nullable=False)
    trade_specialty = db.Column(db.String(128), nullable=True)  # e.g. "electrical", "structural steel"
    tax_registration_number = db.Column(db.String(64), nullable=True)
    status = db.Column(db.String(16), nullable=False, default="active")

    agreements = relationship("SubcontractAgreement", back_populates="subcontractor", cascade="all, delete-orphan")
    compliance_documents = relationship("ComplianceDocument", back_populates="subcontractor", cascade="all, delete-orphan")

    __table_args__ = (db.CheckConstraint(f"status IN {SUBCONTRACTOR_STATUSES}", name="ck_sub_subcontractors_status"),)


class SubcontractAgreement(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """SUB-01: mirrors Module 4's Contract structure (value, payment
    terms, retention terms) but scoped to a subcontract package."""

    __tablename__ = "sub_agreements"

    subcontractor_id = db.Column(UUID(as_uuid=True), db.ForeignKey("sub_subcontractors.id"), nullable=False, index=True)
    contract_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)  # ctm_contracts.id, loose reference

    agreement_number = db.Column(db.String(128), nullable=False)
    value = db.Column(db.Numeric(18, 4), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="NGN")
    payment_terms_summary = db.Column(db.Text, nullable=True)
    retention_percentage = db.Column(db.Numeric(5, 2), nullable=False, default=5)
    status = db.Column(db.String(16), nullable=False, default="active", index=True)

    subcontractor = relationship("Subcontractor", back_populates="agreements")
    scope_items = relationship("SubcontractScopeItem", back_populates="agreement", cascade="all, delete-orphan")
    retention = relationship("SubcontractRetention", back_populates="agreement", uselist=False)

    __table_args__ = (
        db.CheckConstraint(f"status IN {AGREEMENT_STATUSES}", name="ck_sub_agreements_status"),
        db.UniqueConstraint("tenant_id", "agreement_number", name="uq_sub_agreements_tenant_number"),
    )


class SubcontractScopeItem(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """SUB-02: BOQ-item-level or lump-sum scope, linked to the main
    contract's CBS for cost-code alignment (loose reference)."""

    __tablename__ = "sub_scope_items"

    agreement_id = db.Column(UUID(as_uuid=True), db.ForeignKey("sub_agreements.id"), nullable=False, index=True)
    boq_item_id = db.Column(UUID(as_uuid=True), nullable=True)  # loose reference
    cbs_line_item_id = db.Column(UUID(as_uuid=True), nullable=True)  # est_cbs_line_items.id, loose reference

    description = db.Column(db.Text, nullable=False)
    is_lump_sum = db.Column(db.Boolean, nullable=False, default=False)
    quantity = db.Column(db.Numeric(18, 4), nullable=True)  # null if lump sum
    unit = db.Column(db.String(32), nullable=True)
    rate = db.Column(db.Numeric(18, 4), nullable=True)  # null if lump sum
    lump_sum_amount = db.Column(db.Numeric(18, 4), nullable=True)  # null if unit-rate

    agreement = relationship("SubcontractAgreement", back_populates="scope_items")


class SubcontractProgressEntry(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """SUB-03: self-measured progress submission, routed for
    main-contractor verification (into a MeasurementSheet) before any
    certification can reference it."""

    __tablename__ = "sub_progress_entries"

    agreement_id = db.Column(UUID(as_uuid=True), db.ForeignKey("sub_agreements.id"), nullable=False, index=True)
    scope_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey("sub_scope_items.id"), nullable=True)

    submitted_quantity = db.Column(db.Numeric(18, 4), nullable=False)
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    submitted_by = db.Column(UUID(as_uuid=True), nullable=True)  # the subcontractor's representative
    status = db.Column(db.String(16), nullable=False, default="submitted")

    __table_args__ = (db.CheckConstraint(f"status IN {PROGRESS_STATUSES}", name="ck_sub_progress_status"),)


class MeasurementSheet(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """SUB-04: verified quantities, jointly referenced by both parties.
    This is what a PaymentCertificateLine must reference -- see the
    business rule in services.issue_payment_certificate."""

    __tablename__ = "sub_measurement_sheets"

    agreement_id = db.Column(UUID(as_uuid=True), db.ForeignKey("sub_agreements.id"), nullable=False, index=True)
    scope_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey("sub_scope_items.id"), nullable=False, index=True)
    progress_entry_id = db.Column(UUID(as_uuid=True), db.ForeignKey("sub_progress_entries.id"), nullable=True)

    verified_quantity = db.Column(db.Numeric(18, 4), nullable=False)
    measured_by = db.Column(UUID(as_uuid=True), nullable=True)  # main contractor's rep
    subcontractor_countersigned_by = db.Column(UUID(as_uuid=True), nullable=True)
    measured_at = db.Column(db.DateTime(timezone=True), nullable=True)
    status = db.Column(db.String(16), nullable=False, default="draft")

    __table_args__ = (db.CheckConstraint(f"status IN {MEASUREMENT_SHEET_STATUSES}", name="ck_sub_measurement_status"),)


class PaymentCertificate(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """SUB-05: generated from verified measurement, applying retention
    and any back-charges."""

    __tablename__ = "sub_payment_certificates"

    agreement_id = db.Column(UUID(as_uuid=True), db.ForeignKey("sub_agreements.id"), nullable=False, index=True)
    certificate_number = db.Column(db.String(128), nullable=False)
    period_start = db.Column(db.Date, nullable=True)
    period_end = db.Column(db.Date, nullable=True)

    gross_certified_amount = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    retention_withheld = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    back_charges_total = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    net_payable = db.Column(db.Numeric(18, 4), nullable=False, default=0)

    status = db.Column(db.String(16), nullable=False, default="draft")
    issued_at = db.Column(db.DateTime(timezone=True), nullable=True)

    compliance_waiver = db.Column(db.Boolean, nullable=False, default=False)
    compliance_waiver_reason = db.Column(db.Text, nullable=True)
    compliance_waiver_by = db.Column(UUID(as_uuid=True), nullable=True)

    lines = relationship("PaymentCertificateLine", back_populates="certificate", cascade="all, delete-orphan")
    back_charges = relationship("BackCharge", back_populates="certificate")

    __table_args__ = (
        db.CheckConstraint(f"status IN {CERTIFICATE_STATUSES}", name="ck_sub_certificates_status"),
        db.UniqueConstraint("tenant_id", "certificate_number", name="uq_sub_certificates_tenant_number"),
    )


class PaymentCertificateLine(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """Each line MUST reference a verified MeasurementSheet -- the
    data-layer half of the business rule (the FK doesn't enforce
    "verified" status by itself; services.py checks that)."""

    __tablename__ = "sub_payment_certificate_lines"

    certificate_id = db.Column(UUID(as_uuid=True), db.ForeignKey("sub_payment_certificates.id"), nullable=False, index=True)
    measurement_sheet_id = db.Column(UUID(as_uuid=True), db.ForeignKey("sub_measurement_sheets.id"), nullable=False)

    certified_quantity = db.Column(db.Numeric(18, 4), nullable=False)
    rate = db.Column(db.Numeric(18, 4), nullable=False)
    amount = db.Column(db.Numeric(18, 4), nullable=False)

    certificate = relationship("PaymentCertificate", back_populates="lines")


class BackCharge(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """SUB-10: itemized deduction (rework, materials supplied, etc.),
    applied on the next Payment Certificate."""

    __tablename__ = "sub_back_charges"

    agreement_id = db.Column(UUID(as_uuid=True), db.ForeignKey("sub_agreements.id"), nullable=False, index=True)
    payment_certificate_id = db.Column(UUID(as_uuid=True), db.ForeignKey("sub_payment_certificates.id"), nullable=True)

    description = db.Column(db.Text, nullable=False)
    amount = db.Column(db.Numeric(18, 4), nullable=False)
    reason_category = db.Column(db.String(24), nullable=False, default="other")
    raised_at = db.Column(db.DateTime(timezone=True), nullable=True)
    raised_by = db.Column(UUID(as_uuid=True), nullable=True)

    certificate = relationship("PaymentCertificate", back_populates="back_charges")

    __table_args__ = (db.CheckConstraint(f"reason_category IN {BACK_CHARGE_CATEGORIES}", name="ck_sub_back_charges_category"),)


class SubcontractRetention(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """SUB-06: business rule -- release is a distinct approval step,
    independent of but reconcilable against the main contract's
    retention. See module docstring for why no cross-call to CTM exists."""

    __tablename__ = "sub_retentions"

    agreement_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("sub_agreements.id"), nullable=False, unique=True, index=True
    )
    percentage = db.Column(db.Numeric(5, 2), nullable=False)
    amount_withheld = db.Column(db.Numeric(18, 4), nullable=False, default=0)

    release_substantial_completion_pct = db.Column(db.Numeric(5, 2), nullable=False, default=50)
    release_final_pct = db.Column(db.Numeric(5, 2), nullable=False, default=50)
    released_substantial_completion = db.Column(db.Boolean, nullable=False, default=False)
    released_final = db.Column(db.Boolean, nullable=False, default=False)

    agreement = relationship("SubcontractAgreement", back_populates="retention")

    __table_args__ = (
        db.CheckConstraint(
            "release_substantial_completion_pct + release_final_pct = 100",
            name="ck_sub_retentions_release_sums_100",
        ),
    )


class SubcontractClaim(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """SUB-07: delay/additional-scope claims with a structured review
    workflow."""

    __tablename__ = "sub_claims"

    agreement_id = db.Column(UUID(as_uuid=True), db.ForeignKey("sub_agreements.id"), nullable=False, index=True)

    claim_type = db.Column(db.String(24), nullable=False)
    description = db.Column(db.Text, nullable=False)
    claimed_amount = db.Column(db.Numeric(18, 4), nullable=True)
    claimed_days = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="submitted")
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    reviewed_by = db.Column(UUID(as_uuid=True), nullable=True)
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    response_notes = db.Column(db.Text, nullable=True)

    __table_args__ = (
        db.CheckConstraint(f"claim_type IN {CLAIM_TYPES}", name="ck_sub_claims_type"),
        db.CheckConstraint(f"status IN {CLAIM_STATUSES}", name="ck_sub_claims_status"),
    )


class PerformanceRating(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """SUB-08: quality/schedule/safety/responsiveness, per subcontractor
    per project."""

    __tablename__ = "sub_performance_ratings"

    subcontractor_id = db.Column(UUID(as_uuid=True), db.ForeignKey("sub_subcontractors.id"), nullable=False, index=True)
    project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)
    period_label = db.Column(db.String(32), nullable=True)  # e.g. "2026-Q1"

    quality_score = db.Column(db.Numeric(4, 1), nullable=False)  # 0-10
    schedule_score = db.Column(db.Numeric(4, 1), nullable=False)
    safety_score = db.Column(db.Numeric(4, 1), nullable=False)
    responsiveness_score = db.Column(db.Numeric(4, 1), nullable=False)
    overall_score = db.Column(db.Numeric(4, 2), nullable=False)  # average of the four, computed at save time

    rated_by = db.Column(UUID(as_uuid=True), nullable=True)
    rated_at = db.Column(db.DateTime(timezone=True), nullable=True)


class ComplianceDocument(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """SUB-09: business rule -- blocks new payment certification if
    expired, absent an explicit waiver (same pattern as PRC's vendor
    compliance gate on PO issuance)."""

    __tablename__ = "sub_compliance_documents"

    subcontractor_id = db.Column(UUID(as_uuid=True), db.ForeignKey("sub_subcontractors.id"), nullable=False, index=True)
    document_id = db.Column(UUID(as_uuid=True), db.ForeignKey("documents.id"), nullable=True)
    doc_type = db.Column(db.String(32), nullable=False)
    valid_until = db.Column(db.Date, nullable=True, index=True)

    subcontractor = relationship("Subcontractor", back_populates="compliance_documents")

    __table_args__ = (db.CheckConstraint(f"doc_type IN {COMPLIANCE_DOC_TYPES}", name="ck_sub_compliance_doc_type"),)
