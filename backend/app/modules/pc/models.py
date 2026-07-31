"""
Module 19 — Project Controls (Code: PC)
SRS Section 4.19.

The module intended to distinguish SiteForge from generic ERPs: a
single dashboard where schedule, cost, and risk data from every other
module converge into standard Earned Value Management analytics.

Key Data Entities (SRS 4.19): EVMSnapshot, ScheduleVarianceRecord,
CostVarianceRecord, ForecastAtCompletion, CashFlowForecast,
RiskRegisterEntry, DelayAnalysisSummary.

Design notes:
  - `ScheduleVarianceRecord` and `CostVarianceRecord` are NOT separate
    tables here -- SV and CV are two numbers derived from the same
    PV/EV/AC triad as CPI and SPI, computed and stored together on
    `EVMSnapshot`. Nothing in the SRS describes an independent
    lifecycle for a variance record (no approval workflow, no
    corrective-action linkage distinct from the snapshot itself) the
    way NCR/CorrectiveAction genuinely have separate lifecycles in
    Module 13 -- splitting them out would just be two more rows with
    the same foreign key and no behavior of their own.
  - PV, EV, AC, and BAC are caller-supplied to `EVMSnapshot` creation,
    not computed by this module directly: PV comes from Module 5's
    baseline, EV from Module 6's physical progress, AC from Module 17's
    posted costs, BAC from Module 3's CBS budget. This module's actual
    job -- and what makes it real rather than a passthrough -- is the
    derived arithmetic (CV, SV, CPI, SPI) computed from those inputs,
    which is what services.py does and what gets tested.
  - Business rule (SRS 4.19): EVM snapshots are immutable historical
    records once created -- there is no update route anywhere in this
    module. Re-running the calculation for the same `period_end` at a
    later date (potentially against a changed baseline) creates a NEW
    snapshot rather than overwriting the old one, which is exactly what
    "recalculable at any prior period-end for audit purposes" requires:
    the audit trail is the sequence of snapshots, not a single mutable
    number.
  - `ProjectCashFlowForecast` (PC-07) is a project-level forecast,
    deliberately distinct from Module 17's company-level
    CashFlowForecastEntry -- combining committed costs, planned
    billing, and payment terms is a project-controls concern even
    though the underlying cash figures ultimately roll up into
    Module 17's company-wide forecast.
"""
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin


FORECAST_METHODS = ("cpi_based", "atypical_variance", "manual")
RISK_STATUSES = ("open", "mitigated", "closed")
DELAY_CLASSIFICATIONS = ("schedule_driven", "cost_driven", "both", "neither")


class EVMSnapshot(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PC-01 through PC-05: an immutable historical EVM calculation.
    Business rule -- never updated once created; a later recalculation
    for the same period_end is a new row."""

    __tablename__ = "pc_evm_snapshots"

    project_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    period_end = db.Column(db.Date, nullable=False, index=True)
    baseline_id = db.Column(UUID(as_uuid=True), nullable=True)  # pln_baselines.id, loose reference, for audit trail

    planned_value = db.Column(db.Numeric(18, 4), nullable=False)
    earned_value = db.Column(db.Numeric(18, 4), nullable=False)
    actual_cost = db.Column(db.Numeric(18, 4), nullable=False)
    budget_at_completion = db.Column(db.Numeric(18, 4), nullable=False)

    # Derived (PC-04, PC-05) -- computed in services.py, never
    # accepted directly from a caller.
    cost_variance = db.Column(db.Numeric(18, 4), nullable=False)
    schedule_variance = db.Column(db.Numeric(18, 4), nullable=False)
    cpi = db.Column(db.Numeric(8, 4), nullable=True)  # null if AC == 0
    spi = db.Column(db.Numeric(8, 4), nullable=True)  # null if PV == 0

    calculated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    calculated_by = db.Column(UUID(as_uuid=True), nullable=True)

    forecasts = relationship("ForecastAtCompletion", back_populates="snapshot", cascade="all, delete-orphan")


class ForecastAtCompletion(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PC-06: EAC/ETC/VAC, tied to the specific EVMSnapshot it was
    derived from, with a configurable method."""

    __tablename__ = "pc_forecasts_at_completion"

    evm_snapshot_id = db.Column(UUID(as_uuid=True), db.ForeignKey("pc_evm_snapshots.id"), nullable=False, index=True)
    method = db.Column(db.String(24), nullable=False, default="cpi_based")

    estimate_at_completion = db.Column(db.Numeric(18, 4), nullable=False)  # EAC
    estimate_to_complete = db.Column(db.Numeric(18, 4), nullable=False)  # ETC
    variance_at_completion = db.Column(db.Numeric(18, 4), nullable=False)  # VAC = BAC - EAC
    manual_reestimate_reason = db.Column(db.Text, nullable=True)  # required when method == "manual"

    snapshot = relationship("EVMSnapshot", back_populates="forecasts")

    __table_args__ = (db.CheckConstraint(f"method IN {FORECAST_METHODS}", name="ck_pc_forecast_method"),)


class RiskRegisterEntry(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PC-08: probability, impact, exposure value, and mitigation
    owner, feeding EST-09's risk allowance and informing forecast
    confidence."""

    __tablename__ = "pc_risk_register_entries"

    project_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    probability = db.Column(db.Numeric(5, 4), nullable=False)  # 0.0000-1.0000
    impact_value = db.Column(db.Numeric(18, 4), nullable=False)
    exposure_value = db.Column(db.Numeric(18, 4), nullable=False)  # probability * impact_value
    mitigation_owner = db.Column(UUID(as_uuid=True), nullable=True)
    status = db.Column(db.String(16), nullable=False, default="open")
    identified_at = db.Column(db.Date, nullable=True)

    __table_args__ = (
        db.CheckConstraint("probability >= 0 AND probability <= 1", name="ck_pc_risk_probability_range"),
        db.CheckConstraint(f"status IN {RISK_STATUSES}", name="ck_pc_risk_status"),
    )


class DelayAnalysisSummary(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PC-09: summarizes schedule delay (Module 5, loose reference)
    alongside cost variance, distinguishing schedule-driven from
    cost-driven performance issues."""

    __tablename__ = "pc_delay_analysis_summaries"

    project_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    evm_snapshot_id = db.Column(UUID(as_uuid=True), db.ForeignKey("pc_evm_snapshots.id"), nullable=True)
    period_end = db.Column(db.Date, nullable=False)

    total_float_consumed_days = db.Column(db.Integer, nullable=True)  # from Module 5, loose/caller-supplied
    critical_path_delay_days = db.Column(db.Integer, nullable=True)
    classification = db.Column(db.String(16), nullable=False)

    __table_args__ = (db.CheckConstraint(f"classification IN {DELAY_CLASSIFICATIONS}", name="ck_pc_delay_classification"),)


class ProjectCashFlowForecast(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PC-07: rolling forecast combining committed costs, planned
    billing, and payment terms -- see module docstring for why this is
    distinct from Module 17's company-level cash flow entity."""

    __tablename__ = "pc_project_cash_flow_forecasts"

    project_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)

    committed_costs = db.Column(db.Numeric(18, 4), nullable=False, default=0)  # from Module 7 open POs, caller-supplied
    planned_billing = db.Column(db.Numeric(18, 4), nullable=False, default=0)  # from Module 18 schedule, caller-supplied
    net_cash_flow = db.Column(db.Numeric(18, 4), nullable=False, default=0)  # planned_billing - committed_costs

    generated_at = db.Column(db.DateTime(timezone=True), nullable=True)
