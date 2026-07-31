"""
Module 10 — Fuel Management (Code: FUEL)
SRS Section 4.10.

A dedicated module given how materially fuel cost and fuel-related
fraud affect contractor margins in the target market (SRS's own
framing) -- theft detection is not an afterthought here, it's most of
the point.

Key Data Entities (SRS 4.10): FuelPurchase, FuelTank, FuelIssue,
FuelVarianceRecord, TheftFlag.

Design notes:
  - `FuelBurnRateProfile` is not in the SRS's named entity list but is
    the necessary source of the "historical/manufacturer burn rate"
    FUEL-04 requires to compute expected consumption -- without a
    stored expected rate, "variance" has nothing to be variance FROM.
  - `equipment_id` fields are loose references to Module 9's Equipment
    (no FK) -- bounded-context discipline (SRS 3.3). Hours-operated
    figures needed for variance calculation are supplied by the caller
    at call time, the same pattern already used throughout (EXE's
    contracted_quantity, PRC's remaining_budget, EQP's fuel_cost).
  - Business rule (SRS 4.10): a Fuel Variance rolls into EQP-10's Cost
    per Hour as a DISTINCT line, never blended into a generic fuel cost
    figure -- see services.fuel_cost_breakdown, which is what
    app.modules.eqp.services.calculate_cost_per_hour now accepts as two
    separate figures (fuel_normal_cost, fuel_variance_cost) rather than
    one blended fuel_cost.
"""
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin


TANK_TYPES = ("bulk_storage", "equipment_onboard")
THEFT_FLAG_REASONS = ("variance_threshold_exceeded", "no_usage_log", "tank_level_mismatch")
THEFT_FLAG_STATUSES = ("open", "reviewing", "resolved", "escalated")


class FuelTank(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """FUEL-02: bulk storage tanks and equipment onboard tanks."""

    __tablename__ = "fuel_tanks"

    name = db.Column(db.String(255), nullable=False)
    tank_type = db.Column(db.String(24), nullable=False)
    capacity_litres = db.Column(db.Numeric(10, 2), nullable=True)
    current_level_litres = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)
    equipment_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)  # eqp_equipment.id, for onboard tanks

    purchases = relationship("FuelPurchase", back_populates="tank", cascade="all, delete-orphan")
    issues = relationship("FuelIssue", back_populates="tank", cascade="all, delete-orphan")

    __table_args__ = (db.CheckConstraint(f"tank_type IN {TANK_TYPES}", name="ck_fuel_tanks_type"),)


class FuelPurchase(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """FUEL-01: purchase record; confirming delivery updates the tank
    balance."""

    __tablename__ = "fuel_purchases"

    tank_id = db.Column(UUID(as_uuid=True), db.ForeignKey("fuel_tanks.id"), nullable=False, index=True)
    vendor_id = db.Column(UUID(as_uuid=True), nullable=True)  # prc_vendors.id, loose reference

    quantity_litres = db.Column(db.Numeric(10, 2), nullable=False)
    unit_price = db.Column(db.Numeric(10, 4), nullable=False)
    total_cost = db.Column(db.Numeric(18, 4), nullable=False)

    delivered_at = db.Column(db.DateTime(timezone=True), nullable=True)
    delivery_confirmed = db.Column(db.Boolean, nullable=False, default=False)
    confirmed_by = db.Column(UUID(as_uuid=True), nullable=True)

    tank = relationship("FuelTank", back_populates="purchases")


class FuelIssue(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """FUEL-03/FUEL-09: fuel issued to equipment, with a meter reading
    at time of issue and a countersignature requirement above a
    configurable threshold (business rule)."""

    __tablename__ = "fuel_issues"

    tank_id = db.Column(UUID(as_uuid=True), db.ForeignKey("fuel_tanks.id"), nullable=False, index=True)
    equipment_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)  # eqp_equipment.id, loose reference
    operator_id = db.Column(UUID(as_uuid=True), nullable=True)  # Module 11, loose reference

    quantity_litres = db.Column(db.Numeric(10, 2), nullable=False)
    meter_reading = db.Column(db.Numeric(12, 2), nullable=True)  # odometer or hour-meter
    issued_at = db.Column(db.DateTime(timezone=True), nullable=False)
    issued_by = db.Column(UUID(as_uuid=True), nullable=True)

    requires_countersignature = db.Column(db.Boolean, nullable=False, default=False)
    countersigned = db.Column(db.Boolean, nullable=False, default=False)
    countersigned_by = db.Column(UUID(as_uuid=True), nullable=True)
    countersigned_at = db.Column(db.DateTime(timezone=True), nullable=True)

    tank = relationship("FuelTank", back_populates="issues")


class FuelBurnRateProfile(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """The expected-consumption baseline FUEL-04 compares actual issues
    against -- without this, "variance" has nothing to be variance
    from (see module docstring)."""

    __tablename__ = "fuel_burn_rate_profiles"

    equipment_id = db.Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    expected_litres_per_hour = db.Column(db.Numeric(8, 2), nullable=False)
    source = db.Column(db.String(24), nullable=False, default="historical")  # historical | manufacturer


class FuelVarianceRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """FUEL-04: computed per equipment unit per period -- see
    services.calculate_fuel_variance for the calculation. Stored (not
    purely computed-on-read like EQP's Cost per Hour) because variance
    records are themselves a reportable audit trail (FUEL-07), not just
    a momentary display figure."""

    __tablename__ = "fuel_variance_records"

    equipment_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)

    expected_litres = db.Column(db.Numeric(10, 2), nullable=False)
    actual_litres = db.Column(db.Numeric(10, 2), nullable=False)
    variance_litres = db.Column(db.Numeric(10, 2), nullable=False)
    variance_pct = db.Column(db.Numeric(6, 2), nullable=True)  # null if expected == 0
    unit_price_used = db.Column(db.Numeric(10, 4), nullable=True)
    variance_cost = db.Column(db.Numeric(18, 4), nullable=True)

    __table_args__ = (
        db.UniqueConstraint("equipment_id", "period_start", "period_end", name="uq_fuel_variance_equipment_period"),
    )


class TheftFlag(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """FUEL-05, business rule: does not auto-block operations, but
    generates a mandatory review task, escalating to Executive
    Dashboard visibility if unresolved beyond a configurable period."""

    __tablename__ = "fuel_theft_flags"

    equipment_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)
    tank_id = db.Column(UUID(as_uuid=True), db.ForeignKey("fuel_tanks.id"), nullable=True)
    fuel_issue_id = db.Column(UUID(as_uuid=True), db.ForeignKey("fuel_issues.id"), nullable=True)

    flag_reason = db.Column(db.String(32), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="open", index=True)
    assigned_to = db.Column(UUID(as_uuid=True), nullable=True)  # Fleet/Plant Manager

    raised_at = db.Column(db.DateTime(timezone=True), nullable=True)
    resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    escalated_at = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        db.CheckConstraint(f"flag_reason IN {THEFT_FLAG_REASONS}", name="ck_fuel_theft_flags_reason"),
        db.CheckConstraint(f"status IN {THEFT_FLAG_STATUSES}", name="ck_fuel_theft_flags_status"),
    )
