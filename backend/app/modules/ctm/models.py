"""
Module 4 — Contract Management (Code: CTM)
SRS Section 4.4.

Governs the contract that comes into force once a bid is won, including
the commercial instruments (bonds, guarantees, retention) that
construction contracts depend on.

Key Data Entities (SRS 4.4): Contract, ContractDocument, PaymentTerm,
PerformanceBond, AdvancePayment, Retention, Insurance, Guarantee,
ContractAmendment.

This module is what closes the loop Module 1/2 leave open: BDC's
Opportunity.contract_id and the "won" transition business rule
(app/modules/bdc/services.py) exist but nothing populated a real
Contract until now. See services.create_contract_on_award for the
call other modules should make.
"""
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin, SoftDeleteMixin


CONTRACT_STATUSES = ("active", "completed", "terminated")
INSTRUMENT_STATUSES = ("active", "released", "expired", "claimed")
RETENTION_RELEASE_STAGES = ("substantial_completion", "end_of_dlp")
AMENDMENT_TYPES = ("time", "price", "scope")
AMENDMENT_STATUSES = ("approved", "pending", "rejected")


class Contract(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin, SoftDeleteMixin):
    """CTM-01, CTM-02, CTM-10, CTM-11: the contract record itself."""

    __tablename__ = "ctm_contracts"

    tender_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)  # tbm_tenders.id
    cbs_id = db.Column(UUID(as_uuid=True), nullable=True)  # est_cost_breakdown_structures.id (baseline)
    project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)  # projects.id, once created

    contract_number = db.Column(db.String(128), nullable=False)
    contract_value = db.Column(db.Numeric(18, 4), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="NGN")
    base_currency = db.Column(db.String(3), nullable=False, default="NGN")  # CTM-11: consolidated reporting

    payment_cycle_days = db.Column(db.Integer, nullable=True)  # e.g. 30
    certification_frequency = db.Column(db.String(32), nullable=True)  # e.g. "monthly"

    status = db.Column(db.String(16), nullable=False, default="active", index=True)
    start_date = db.Column(db.Date, nullable=True)
    completion_date = db.Column(db.Date, nullable=True, index=True)  # CTM-10, incl. EOT-adjusted
    original_completion_date = db.Column(db.Date, nullable=True)  # snapshot, before any EOT

    documents = relationship("ContractDocument", back_populates="contract", cascade="all, delete-orphan")
    payment_terms = relationship("PaymentTerm", back_populates="contract", cascade="all, delete-orphan")
    performance_bonds = relationship("PerformanceBond", back_populates="contract", cascade="all, delete-orphan")
    advance_payments = relationship("AdvancePayment", back_populates="contract", cascade="all, delete-orphan")
    retentions = relationship("Retention", back_populates="contract", cascade="all, delete-orphan")
    insurances = relationship("Insurance", back_populates="contract", cascade="all, delete-orphan")
    guarantees = relationship("Guarantee", back_populates="contract", cascade="all, delete-orphan")
    amendments = relationship("ContractAmendment", back_populates="contract", cascade="all, delete-orphan")

    __table_args__ = (
        db.CheckConstraint(f"status IN {CONTRACT_STATUSES}", name="ck_ctm_contracts_status"),
        db.UniqueConstraint("tenant_id", "contract_number", name="uq_ctm_contracts_tenant_number"),
        db.UniqueConstraint("tenant_id", "tender_id", name="uq_ctm_contracts_tenant_tender"),
    )


class ContractDocument(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """CTM-03: executed contract documents repository."""

    __tablename__ = "ctm_contract_documents"

    contract_id = db.Column(UUID(as_uuid=True), db.ForeignKey("ctm_contracts.id"), nullable=False, index=True)
    document_id = db.Column(UUID(as_uuid=True), db.ForeignKey("documents.id"), nullable=True)
    doc_type = db.Column(db.String(64), nullable=False)  # signed_agreement | conditions | drawings_register | other

    contract = relationship("Contract", back_populates="documents")


class PaymentTerm(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """CTM-02: structured payment terms beyond the summary fields on
    Contract itself (e.g. milestone-based terms alongside the default
    monthly-certification cycle)."""

    __tablename__ = "ctm_payment_terms"

    contract_id = db.Column(UUID(as_uuid=True), db.ForeignKey("ctm_contracts.id"), nullable=False, index=True)
    description = db.Column(db.String(255), nullable=False)
    trigger = db.Column(db.String(255), nullable=True)  # e.g. "Milestone: substructure complete"
    amount = db.Column(db.Numeric(18, 4), nullable=True)
    percentage_of_contract_value = db.Column(db.Numeric(5, 2), nullable=True)

    contract = relationship("Contract", back_populates="payment_terms")


class PerformanceBond(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """CTM-04: performance bond with expiry tracking."""

    __tablename__ = "ctm_performance_bonds"

    contract_id = db.Column(UUID(as_uuid=True), db.ForeignKey("ctm_contracts.id"), nullable=False, index=True)
    amount = db.Column(db.Numeric(18, 4), nullable=False)
    issuing_bank = db.Column(db.String(255), nullable=True)
    valid_from = db.Column(db.Date, nullable=True)
    valid_until = db.Column(db.Date, nullable=True, index=True)
    status = db.Column(db.String(16), nullable=False, default="active")

    contract = relationship("Contract", back_populates="performance_bonds")

    __table_args__ = (db.CheckConstraint(f"status IN {INSTRUMENT_STATUSES}", name="ck_ctm_perf_bonds_status"),)


class AdvancePayment(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """CTM-05: advance payment terms and recoupment tracking. Recoupment
    against each certified payment is calculated in services.py (feeds
    Module 18 Client Billing certificates)."""

    __tablename__ = "ctm_advance_payments"

    contract_id = db.Column(UUID(as_uuid=True), db.ForeignKey("ctm_contracts.id"), nullable=False, index=True)
    percentage_of_contract_value = db.Column(db.Numeric(5, 2), nullable=False)
    amount = db.Column(db.Numeric(18, 4), nullable=False)
    recoupment_pct_per_certificate = db.Column(db.Numeric(5, 2), nullable=False)  # % of each cert clawed back
    amount_recouped = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    paid_at = db.Column(db.Date, nullable=True)

    contract = relationship("Contract", back_populates="advance_payments")

    @property
    def outstanding_balance(self):
        return (self.amount or 0) - (self.amount_recouped or 0)


class Retention(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """CTM-06: retention percentage/cap and release schedule. Business
    rule: amount_withheld must always equal the sum of retention amounts
    deducted across all certified payment certificates for this
    contract (reconciled at every certificate approval, in
    services.py -- this module doesn't own certificates, Module 18
    does, so reconciliation here is a read-only check against a total
    Module 18 reports, not a live join across bounded contexts)."""

    __tablename__ = "ctm_retentions"

    contract_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("ctm_contracts.id"), nullable=False, unique=True, index=True
    )
    percentage = db.Column(db.Numeric(5, 2), nullable=False)
    cap_amount = db.Column(db.Numeric(18, 4), nullable=True)
    amount_withheld = db.Column(db.Numeric(18, 4), nullable=False, default=0)

    # Release schedule, e.g. 50% at substantial completion, 50% at end of DLP.
    release_substantial_completion_pct = db.Column(db.Numeric(5, 2), nullable=False, default=50)
    release_end_of_dlp_pct = db.Column(db.Numeric(5, 2), nullable=False, default=50)
    released_substantial_completion = db.Column(db.Boolean, nullable=False, default=False)
    released_end_of_dlp = db.Column(db.Boolean, nullable=False, default=False)

    contract = relationship("Contract", back_populates="retentions")

    __table_args__ = (
        db.CheckConstraint(
            "release_substantial_completion_pct + release_end_of_dlp_pct = 100",
            name="ck_ctm_retentions_release_sums_100",
        ),
    )


class Insurance(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """CTM-07: required insurance policies (CAR, third-party liability,
    workmen's compensation) with expiry tracking."""

    __tablename__ = "ctm_insurances"

    contract_id = db.Column(UUID(as_uuid=True), db.ForeignKey("ctm_contracts.id"), nullable=False, index=True)
    policy_type = db.Column(db.String(64), nullable=False)  # CAR | third_party_liability | workmens_compensation | other
    insurer = db.Column(db.String(255), nullable=True)
    coverage_amount = db.Column(db.Numeric(18, 4), nullable=True)
    valid_from = db.Column(db.Date, nullable=True)
    valid_until = db.Column(db.Date, nullable=True, index=True)
    status = db.Column(db.String(16), nullable=False, default="active")

    contract = relationship("Contract", back_populates="insurances")

    __table_args__ = (db.CheckConstraint(f"status IN {INSTRUMENT_STATUSES}", name="ck_ctm_insurances_status"),)


class Guarantee(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """CTM-08: advance payment guarantee, retention guarantee, etc. --
    same lifecycle controls (expiry alerts) as PerformanceBond."""

    __tablename__ = "ctm_guarantees"

    contract_id = db.Column(UUID(as_uuid=True), db.ForeignKey("ctm_contracts.id"), nullable=False, index=True)
    guarantee_type = db.Column(db.String(64), nullable=False)  # advance_payment | retention | other
    amount = db.Column(db.Numeric(18, 4), nullable=False)
    issuing_bank = db.Column(db.String(255), nullable=True)
    valid_from = db.Column(db.Date, nullable=True)
    valid_until = db.Column(db.Date, nullable=True, index=True)
    status = db.Column(db.String(16), nullable=False, default="active")

    contract = relationship("Contract", back_populates="guarantees")

    __table_args__ = (db.CheckConstraint(f"status IN {INSTRUMENT_STATUSES}", name="ck_ctm_guarantees_status"),)


class ContractAmendment(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """CTM-09: whole-contract-level amendments (time/price/scope),
    distinct from item-level Variation Orders (Module 18). Time
    amendments (EOTs) additionally update Contract.completion_date via
    services.py, since CTM-10 requires that field to reflect EOTs."""

    __tablename__ = "ctm_contract_amendments"

    contract_id = db.Column(UUID(as_uuid=True), db.ForeignKey("ctm_contracts.id"), nullable=False, index=True)
    amendment_type = db.Column(db.String(16), nullable=False)
    description = db.Column(db.Text, nullable=False)

    # Only the field(s) relevant to amendment_type are populated.
    time_extension_days = db.Column(db.Integer, nullable=True)
    price_delta = db.Column(db.Numeric(18, 4), nullable=True)
    scope_change_description = db.Column(db.Text, nullable=True)

    approved_by = db.Column(UUID(as_uuid=True), nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    # Deliberately defaults to "approved" -- matches the pre-existing
    # behavior for every tenant that hasn't configured a Workflow
    # Engine chain for ("ctm", "contract_amendment"): an amendment
    # took effect immediately on creation, with no real second-approval
    # gate at all (approved_by was always the same actor who created
    # it). Once a tenant activates a workflow for this entity type,
    # new amendments are created "pending" instead and only take
    # effect once the workflow reports approved -- see
    # services.py:record_amendment and finalize_amendment.
    status = db.Column(db.String(16), nullable=False, default="approved")

    contract = relationship("Contract", back_populates="amendments")

    __table_args__ = (
        db.CheckConstraint(f"amendment_type IN {AMENDMENT_TYPES}", name="ck_ctm_amendments_type"),
        db.CheckConstraint(f"status IN {AMENDMENT_STATUSES}", name="ck_ctm_amendments_status"),
    )
