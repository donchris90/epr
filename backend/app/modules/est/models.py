"""
Module 3 — Estimating & Cost Engineering (Code: EST)
SRS Section 4.3.

Converts a scoped BOQ (from Module 2's TenderBOQItem) into a priced,
risk-adjusted tender price, and — on contract award — produces the
baseline Budget and Cost Breakdown Structure that Module 19 (Project
Controls) measures performance against for the rest of the project's
life.

Key Data Entities (SRS 4.3): BOQItem, RateAnalysis, CostLibraryItem,
MaterialPrice, EquipmentRate, LaborRate, VendorQuotation, Markup,
Contingency, RiskAllowance, Budget, CostBreakdownStructure.

Design notes:
  - `EstimateVersion` is not in the SRS's named entity list but is the
    natural home for EST-13 (what-if scenarios) and EST-14 (versioning
    with audit trail): a Tender can have several EstimateVersion rows,
    exactly one of which is the submitted version TBM's estimate-lock
    business rule refers to.
  - `BOQItem` here is EST's own priced/hierarchical BOQ, distinct from
    TBM's `TenderBOQItem` (the raw client-issued list before pricing).
    Each links back to its source TenderBOQItem for traceability, but
    EST does not query tbm_* tables directly for pricing logic --
    consistent with the bounded-context discipline used throughout
    (SRS Section 3.3).
  - `Contingency` and `RiskAllowance` are modeled as one table
    (`ContingencyItem`) distinguished by a `kind` column, since the SRS
    describes them as sibling concepts that must appear "visible
    separately in the final price build-up" -- a shared shape with a
    discriminator satisfies that without duplicating structure.
"""
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin, SoftDeleteMixin


ESTIMATE_VERSION_STATUSES = ("draft", "submitted", "superseded")
RATE_COMPONENT_TYPES = ("material", "labor", "equipment", "subcontract")
CONTINGENCY_KINDS = ("contingency", "risk_allowance")
CONTINGENCY_BASES = ("percentage", "fixed")
MARKUP_SCOPES = ("whole_tender", "section", "item")


class EstimateVersion(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EST-13 (what-if scenarios) / EST-14 (versioning): a Tender may
    have several estimate versions; exactly one may be "submitted" at a
    time, and that is the version TBM's estimate-lock business rule
    (SRS 4.2) applies to."""

    __tablename__ = "est_estimate_versions"

    tender_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)  # tbm_tenders.id
    version_number = db.Column(db.Integer, nullable=False)
    label = db.Column(db.String(255), nullable=True)  # e.g. "Base case", "Fast-track scenario"
    status = db.Column(db.String(16), nullable=False, default="draft", index=True)
    notes = db.Column(db.Text, nullable=True)

    boq_items = relationship("BOQItem", back_populates="estimate_version", cascade="all, delete-orphan")
    markups = relationship("Markup", back_populates="estimate_version", cascade="all, delete-orphan")
    contingency_items = relationship("ContingencyItem", back_populates="estimate_version", cascade="all, delete-orphan")

    __table_args__ = (
        db.CheckConstraint(f"status IN {ESTIMATE_VERSION_STATUSES}", name="ck_est_estimate_versions_status"),
        db.UniqueConstraint("tender_id", "version_number", name="uq_est_estimate_versions_tender_version"),
    )


class BOQItem(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EST-01: hierarchical (section/sub-section/item) priced BOQ."""

    __tablename__ = "est_boq_items"

    estimate_version_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("est_estimate_versions.id"), nullable=False, index=True
    )
    parent_id = db.Column(UUID(as_uuid=True), db.ForeignKey("est_boq_items.id"), nullable=True, index=True)
    source_tender_boq_item_id = db.Column(UUID(as_uuid=True), nullable=True)  # tbm_tender_boq_items.id

    item_code = db.Column(db.String(64), nullable=True)
    description = db.Column(db.Text, nullable=False)
    unit = db.Column(db.String(32), nullable=True)
    quantity = db.Column(db.Numeric(18, 4), nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    # Denormalized, recomputed by services.py whenever the linked
    # RateAnalysis changes -- never edited directly when a RateAnalysis
    # exists, per the reconciliation business rule (SRS 4.3).
    unit_rate = db.Column(db.Numeric(18, 4), nullable=True)

    estimate_version = relationship("EstimateVersion", back_populates="boq_items")
    rate_analysis = relationship("RateAnalysis", back_populates="boq_item", uselist=False, cascade="all, delete-orphan")


class CostLibraryItem(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EST-03: reusable standard rate analysis component, applicable to
    new tenders and adjustable per rate analysis line."""

    __tablename__ = "est_cost_library_items"

    code = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text, nullable=False)
    component_type = db.Column(db.String(16), nullable=False)
    unit = db.Column(db.String(32), nullable=True)
    default_unit_cost = db.Column(db.Numeric(18, 4), nullable=False)

    __table_args__ = (
        db.CheckConstraint(f"component_type IN {RATE_COMPONENT_TYPES}", name="ck_est_cost_library_items_type"),
        db.UniqueConstraint("tenant_id", "code", name="uq_est_cost_library_items_tenant_code"),
    )


class MaterialPrice(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EST-04: location- and time-based material price history,
    supporting escalation assumptions."""

    __tablename__ = "est_material_prices"

    cost_library_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey("est_cost_library_items.id"), nullable=True)
    material_name = db.Column(db.String(255), nullable=False)
    location = db.Column(db.String(128), nullable=True)
    unit = db.Column(db.String(32), nullable=True)
    price = db.Column(db.Numeric(18, 4), nullable=False)
    effective_date = db.Column(db.Date, nullable=False)

    __table_args__ = (
        db.Index("ix_est_material_prices_tenant_material_date", "tenant_id", "material_name", "effective_date"),
    )


class EquipmentRate(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EST-05: owned equipment cost-per-hour (derived from Module 9/10
    data -- pulled in, not computed here) and rental rates."""

    __tablename__ = "est_equipment_rates"

    equipment_type = db.Column(db.String(128), nullable=False)
    source = db.Column(db.String(16), nullable=False, default="owned")  # owned | rental
    cost_per_hour = db.Column(db.Numeric(18, 4), nullable=False)
    effective_date = db.Column(db.Date, nullable=True)

    __table_args__ = (db.CheckConstraint("source IN ('owned','rental')", name="ck_est_equipment_rates_source"),)


class LaborRate(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EST-06: labor costing by trade/grade, including statutory
    on-costs."""

    __tablename__ = "est_labor_rates"

    trade = db.Column(db.String(128), nullable=False)
    grade = db.Column(db.String(64), nullable=True)
    hourly_rate = db.Column(db.Numeric(18, 4), nullable=False)
    statutory_oncost_pct = db.Column(db.Numeric(5, 2), nullable=False, default=0)


class VendorQuotation(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EST-07: vendor quotations compared against estimated
    material/subcontract costs; feeds forward into Module 7
    (Procurement) once a PO is raised against the accepted quote."""

    __tablename__ = "est_vendor_quotations"

    boq_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey("est_boq_items.id"), nullable=True, index=True)
    vendor_name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    quoted_price = db.Column(db.Numeric(18, 4), nullable=False)
    quoted_at = db.Column(db.Date, nullable=True)
    valid_until = db.Column(db.Date, nullable=True)
    is_accepted = db.Column(db.Boolean, nullable=False, default=False)


class RateAnalysis(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EST-02: decomposes a BOQ item's unit rate into material, labor,
    equipment, and subcontract components. Business rule (SRS 4.3):
    material + labor + equipment + subcontract + markup must sum to the
    displayed unit rate within rounding tolerance, enforced at save
    time in services.py -- this table only stores the components; the
    reconciled total lives on BOQItem.unit_rate."""

    __tablename__ = "est_rate_analyses"

    boq_item_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("est_boq_items.id"), nullable=False, unique=True, index=True
    )

    boq_item = relationship("BOQItem", back_populates="rate_analysis")
    lines = relationship("RateAnalysisLine", back_populates="rate_analysis", cascade="all, delete-orphan")


class RateAnalysisLine(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """One material/labor/equipment/subcontract component of a
    RateAnalysis, with quantity-per-unit and unit cost, per EST-02."""

    __tablename__ = "est_rate_analysis_lines"

    rate_analysis_id = db.Column(UUID(as_uuid=True), db.ForeignKey("est_rate_analyses.id"), nullable=False, index=True)
    cost_library_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey("est_cost_library_items.id"), nullable=True)

    component_type = db.Column(db.String(16), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    quantity_per_unit = db.Column(db.Numeric(18, 4), nullable=False)
    unit_cost = db.Column(db.Numeric(18, 4), nullable=False)
    # Denormalized (quantity_per_unit * unit_cost), recomputed at save
    # time -- stored to make save-time reconciliation and read-time
    # display cheap without recomputing from scratch on every read.
    line_total = db.Column(db.Numeric(18, 4), nullable=False)

    rate_analysis = relationship("RateAnalysis", back_populates="lines")

    __table_args__ = (
        db.CheckConstraint(f"component_type IN {RATE_COMPONENT_TYPES}", name="ck_est_rate_analysis_lines_type"),
    )


class Markup(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EST-08: configurable overhead %/profit % markup, applicable at
    BOQ-item, section, or whole-of-tender level."""

    __tablename__ = "est_markups"

    estimate_version_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("est_estimate_versions.id"), nullable=False, index=True
    )
    scope = db.Column(db.String(16), nullable=False, default="whole_tender")
    target_boq_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey("est_boq_items.id"), nullable=True)
    overhead_pct = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    profit_pct = db.Column(db.Numeric(5, 2), nullable=False, default=0)

    estimate_version = relationship("EstimateVersion", back_populates="markups")

    __table_args__ = (db.CheckConstraint(f"scope IN {MARKUP_SCOPES}", name="ck_est_markups_scope"),)


class ContingencyItem(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EST-09: Contingency (percentage or fixed) and Risk Allowance
    (quantified risk-register-based provisioning), sharing a shape but
    distinguished by `kind` so both remain visible separately in the
    final price build-up, as the SRS requires."""

    __tablename__ = "est_contingency_items"

    estimate_version_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("est_estimate_versions.id"), nullable=False, index=True
    )
    kind = db.Column(db.String(16), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    basis = db.Column(db.String(16), nullable=False, default="percentage")
    value = db.Column(db.Numeric(18, 4), nullable=False)  # percentage points, or a fixed currency amount

    estimate_version = relationship("EstimateVersion", back_populates="contingency_items")

    __table_args__ = (
        db.CheckConstraint(f"kind IN {CONTINGENCY_KINDS}", name="ck_est_contingency_items_kind"),
        db.CheckConstraint(f"basis IN {CONTINGENCY_BASES}", name="ck_est_contingency_items_basis"),
    )


class CostBreakdownStructure(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EST-12: generated on contract award, item-for-item from the
    winning EstimateVersion. Business rule (SRS 4.3): immutable once
    approved -- any subsequent change requires a formal BudgetRevision
    record with approval, never a silent edit (enforced in services.py)."""

    __tablename__ = "est_cost_breakdown_structures"

    project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)  # projects.id, once a Project exists
    source_estimate_version_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("est_estimate_versions.id"), nullable=False
    )
    is_approved = db.Column(db.Boolean, nullable=False, default=False)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    approved_by = db.Column(UUID(as_uuid=True), nullable=True)

    line_items = relationship("CBSLineItem", back_populates="cbs", cascade="all, delete-orphan")


class CBSLineItem(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """One baseline budget line, copied item-for-item from a BOQItem at
    CBS generation time (a snapshot, not a live reference -- the whole
    point of a baseline is that it does not move when the estimate is
    later revised)."""

    __tablename__ = "est_cbs_line_items"

    cbs_id = db.Column(UUID(as_uuid=True), db.ForeignKey("est_cost_breakdown_structures.id"), nullable=False, index=True)
    source_boq_item_id = db.Column(UUID(as_uuid=True), nullable=True)  # est_boq_items.id, for traceability only
    description = db.Column(db.Text, nullable=False)
    unit = db.Column(db.String(32), nullable=True)
    quantity = db.Column(db.Numeric(18, 4), nullable=True)
    unit_rate = db.Column(db.Numeric(18, 4), nullable=True)
    budgeted_amount = db.Column(db.Numeric(18, 4), nullable=False)

    cbs = relationship("CostBreakdownStructure", back_populates="line_items")


class BudgetRevision(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """The only sanctioned way to change an approved CBS baseline (SRS
    4.3 business rule) -- a logged, approved delta, never a silent edit."""

    __tablename__ = "est_budget_revisions"

    cbs_id = db.Column(UUID(as_uuid=True), db.ForeignKey("est_cost_breakdown_structures.id"), nullable=False, index=True)
    cbs_line_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey("est_cbs_line_items.id"), nullable=True)
    reason = db.Column(db.Text, nullable=False)
    previous_amount = db.Column(db.Numeric(18, 4), nullable=False)
    revised_amount = db.Column(db.Numeric(18, 4), nullable=False)
    approved_by = db.Column(UUID(as_uuid=True), nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    # Deliberately defaults to "approved" -- matches pre-existing
    # behavior for every tenant that hasn't configured a Workflow
    # Engine chain for ("est", "budget_revision"): a revision took
    # effect immediately on creation, with no real second-approval
    # gate at all (approved_by was always the same actor who created
    # it). Once a tenant activates one, new revisions are created
    # "pending" instead and only take effect once the workflow
    # reports approved -- see services.py:create_budget_revision and
    # finalize_budget_revision. The same pattern as
    # app/modules/ctm/models.py:ContractAmendment and
    # app/modules/hse/models.py:PermitToWork, applied here because
    # this field directly backs CBSLineItem.budgeted_amount -- the
    # same figure app/commitments/services.py computes remaining
    # budget against, making unreviewed self-approval here a real
    # budget-integrity gap, not a cosmetic one.
    status = db.Column(db.String(16), nullable=False, default="approved")
