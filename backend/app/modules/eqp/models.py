"""
Module 9 — Equipment & Fleet Management (Code: EQP)
SRS Section 4.9.

Full plant/vehicle lifecycle: acquisition, GPS tracking, operator
assignment, maintenance, repairs, downtime, and utilization/cost
analytics.

Key Data Entities (SRS 4.9): Equipment, GPSPosition,
FuelConsumptionRecord (owned by Module 10 -- EQP only reads a cost
figure supplied by the caller, see services.calculate_cost_per_hour),
OperatorAssignment, MaintenanceRecord, SparePart, RepairHistory,
DowntimeEvent, UtilizationRecord.

Design notes:
  - `SparePart` (SRS 4.9) is implemented as `SparePartUsage` -- a
    consumption record linking a maintenance/repair event to a Module 8
    MaterialItem (loose reference, no FK -- bounded-context discipline,
    SRS 3.3). The parts CATALOG already exists as Module 8's
    MaterialItem; there is no need for a second one here.
  - Cost per Hour (EQP-10) is a computed view, not a stored column --
    the business rule that it "recalculates automatically whenever a
    contributing record changes" is trivially and robustly satisfied by
    never storing it at all (the same choice already made for EST's
    Engineer's Estimate and Tender Price views).
  - Operator certification data belongs to Module 11 (Workforce
    Management), which doesn't exist yet -- `certification_valid_until`
    is supplied by the caller at assignment time and stored for audit,
    the same pattern used for EXE's contracted_quantity and PRC's
    remaining_budget checks.
"""
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin


OWNERSHIP_TYPES = ("owned", "rented")
EQUIPMENT_STATUSES = ("active", "under_maintenance", "idle", "disposed")
GPS_SOURCES = ("gps_device", "manual")
OPERATOR_ASSIGNMENT_STATUSES = ("active", "completed", "cancelled")
MAINTENANCE_TYPES = ("scheduled", "unscheduled")
MAINTENANCE_STATUSES = ("scheduled", "completed", "overdue")
DOWNTIME_REASONS = ("breakdown", "scheduled_maintenance", "awaiting_parts", "idle_no_work")
TRANSFER_STATUSES = ("pending", "approved", "rejected")


class Equipment(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EQP-01: the equipment register."""

    __tablename__ = "eqp_equipment"

    name = db.Column(db.String(255), nullable=False)
    make = db.Column(db.String(128), nullable=True)
    model = db.Column(db.String(128), nullable=True)
    serial_chassis_number = db.Column(db.String(128), nullable=True)
    ownership_type = db.Column(db.String(16), nullable=False, default="owned")

    acquisition_cost = db.Column(db.Numeric(18, 4), nullable=True)
    acquisition_date = db.Column(db.Date, nullable=True)
    salvage_value = db.Column(db.Numeric(18, 4), nullable=True, default=0)
    useful_life_years = db.Column(db.Integer, nullable=True)

    status = db.Column(db.String(16), nullable=False, default="active", index=True)
    current_project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)

    gps_positions = relationship("GPSPosition", back_populates="equipment", cascade="all, delete-orphan")
    maintenance_records = relationship("MaintenanceRecord", back_populates="equipment", cascade="all, delete-orphan")
    downtime_events = relationship("DowntimeEvent", back_populates="equipment", cascade="all, delete-orphan")
    utilization_records = relationship("UtilizationRecord", back_populates="equipment", cascade="all, delete-orphan")

    __table_args__ = (
        db.CheckConstraint(f"ownership_type IN {OWNERSHIP_TYPES}", name="ck_eqp_equipment_ownership"),
        db.CheckConstraint(f"status IN {EQUIPMENT_STATUSES}", name="ck_eqp_equipment_status"),
    )

    @property
    def annual_depreciation(self):
        """Straight-line depreciation -- the only method the SRS names
        (EQP-01's "depreciation schedule")."""
        if not self.acquisition_cost or not self.useful_life_years:
            return None
        salvage = self.salvage_value or 0
        return (self.acquisition_cost - salvage) / self.useful_life_years


class GPSPosition(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EQP-02: location history for the map view."""

    __tablename__ = "eqp_gps_positions"

    equipment_id = db.Column(UUID(as_uuid=True), db.ForeignKey("eqp_equipment.id"), nullable=False, index=True)
    latitude = db.Column(db.Numeric(9, 6), nullable=False)
    longitude = db.Column(db.Numeric(9, 6), nullable=False)
    recorded_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    source = db.Column(db.String(16), nullable=False, default="gps_device")

    equipment = relationship("Equipment", back_populates="gps_positions")

    __table_args__ = (db.CheckConstraint(f"source IN {GPS_SOURCES}", name="ck_eqp_gps_positions_source"),)


class OperatorAssignment(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EQP-04: business rule -- blocked if the operator's certification
    (Module 11, supplied by the caller) has expired. No override --
    unlike other modules' budget/compliance checks, the SRS states this
    one as an unconditional block."""

    __tablename__ = "eqp_operator_assignments"

    equipment_id = db.Column(UUID(as_uuid=True), db.ForeignKey("eqp_equipment.id"), nullable=False, index=True)
    operator_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)  # Module 11, loose reference

    shift_start = db.Column(db.DateTime(timezone=True), nullable=False)
    shift_end = db.Column(db.DateTime(timezone=True), nullable=True)
    certification_valid_until = db.Column(db.Date, nullable=True)  # snapshot at assignment time, for audit
    status = db.Column(db.String(16), nullable=False, default="active")

    __table_args__ = (
        db.CheckConstraint(f"status IN {OPERATOR_ASSIGNMENT_STATUSES}", name="ck_eqp_operator_assignments_status"),
    )


class MaintenanceRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EQP-05: scheduled and unscheduled maintenance, with due-date
    alerting based on hours/mileage/calendar interval."""

    __tablename__ = "eqp_maintenance_records"

    equipment_id = db.Column(UUID(as_uuid=True), db.ForeignKey("eqp_equipment.id"), nullable=False, index=True)

    maintenance_type = db.Column(db.String(16), nullable=False, default="scheduled")
    description = db.Column(db.Text, nullable=False)

    due_at_hours = db.Column(db.Numeric(10, 1), nullable=True)
    due_at_date = db.Column(db.Date, nullable=True, index=True)
    due_at_mileage = db.Column(db.Numeric(10, 1), nullable=True)

    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    cost = db.Column(db.Numeric(18, 4), nullable=True)
    performed_by = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(16), nullable=False, default="scheduled")

    equipment = relationship("Equipment", back_populates="maintenance_records")
    spare_parts_used = relationship("SparePartUsage", back_populates="maintenance_record", cascade="all, delete-orphan")

    __table_args__ = (
        db.CheckConstraint(f"maintenance_type IN {MAINTENANCE_TYPES}", name="ck_eqp_maintenance_type"),
        db.CheckConstraint(f"status IN {MAINTENANCE_STATUSES}", name="ck_eqp_maintenance_status"),
    )


class SparePartUsage(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EQP-06: parts consumed per maintenance/repair event, linked to
    Module 8's material catalog (loose reference -- see module
    docstring)."""

    __tablename__ = "eqp_spare_part_usages"

    maintenance_record_id = db.Column(UUID(as_uuid=True), db.ForeignKey("eqp_maintenance_records.id"), nullable=False, index=True)
    material_item_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)  # inv_material_items.id

    quantity = db.Column(db.Numeric(18, 4), nullable=False)
    unit_cost = db.Column(db.Numeric(18, 4), nullable=True)  # captured at time of consumption

    maintenance_record = relationship("MaintenanceRecord", back_populates="spare_parts_used")


class RepairHistory(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EQP-07: repair-specific record (cost, downtime, root cause),
    optionally linked back to the MaintenanceRecord that triggered it."""

    __tablename__ = "eqp_repair_history"

    equipment_id = db.Column(UUID(as_uuid=True), db.ForeignKey("eqp_equipment.id"), nullable=False, index=True)
    maintenance_record_id = db.Column(UUID(as_uuid=True), db.ForeignKey("eqp_maintenance_records.id"), nullable=True)

    description = db.Column(db.Text, nullable=False)
    cost = db.Column(db.Numeric(18, 4), nullable=True)
    downtime_hours = db.Column(db.Numeric(8, 2), nullable=True)
    root_cause = db.Column(db.Text, nullable=True)
    repaired_at = db.Column(db.DateTime(timezone=True), nullable=True)


class DowntimeEvent(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EQP-08: downtime with reason classification, distinct from
    productive hours -- the source of truth for EQP-09's Availability
    calculation."""

    __tablename__ = "eqp_downtime_events"

    equipment_id = db.Column(UUID(as_uuid=True), db.ForeignKey("eqp_equipment.id"), nullable=False, index=True)

    reason_classification = db.Column(db.String(24), nullable=False)
    started_at = db.Column(db.DateTime(timezone=True), nullable=False)
    ended_at = db.Column(db.DateTime(timezone=True), nullable=True)  # null while ongoing
    notes = db.Column(db.Text, nullable=True)

    equipment = relationship("Equipment", back_populates="downtime_events")

    __table_args__ = (db.CheckConstraint(f"reason_classification IN {DOWNTIME_REASONS}", name="ck_eqp_downtime_reason"),)


class UtilizationRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EQP-09: raw per-period productive-hours record, from which
    Availability and Utilization are computed (see services.py)."""

    __tablename__ = "eqp_utilization_records"

    equipment_id = db.Column(UUID(as_uuid=True), db.ForeignKey("eqp_equipment.id"), nullable=False, index=True)
    project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)

    record_date = db.Column(db.Date, nullable=False, index=True)
    hours_operated = db.Column(db.Numeric(6, 2), nullable=False, default=0)  # productive hours
    hours_scheduled = db.Column(db.Numeric(6, 2), nullable=False, default=0)  # total scheduled availability window

    equipment = relationship("Equipment", back_populates="utilization_records")


class EquipmentTransfer(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EQP-12: transfer between projects with an approval step and a
    cost-allocation cutover date."""

    __tablename__ = "eqp_equipment_transfers"

    equipment_id = db.Column(UUID(as_uuid=True), db.ForeignKey("eqp_equipment.id"), nullable=False, index=True)
    from_project_id = db.Column(UUID(as_uuid=True), nullable=True)
    to_project_id = db.Column(UUID(as_uuid=True), nullable=False)

    requested_by = db.Column(UUID(as_uuid=True), nullable=True)
    approved_by = db.Column(UUID(as_uuid=True), nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    cutover_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="pending")

    equipment = relationship("Equipment")

    __table_args__ = (db.CheckConstraint(f"status IN {TRANSFER_STATUSES}", name="ck_eqp_transfers_status"),)
