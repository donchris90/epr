"""
Module 16 — Plant & Quarry Management (Code: PQ)
SRS Section 4.16.

The production side of the business for contractors who operate their
own crushers, asphalt plants, concrete batching plants, and quarries --
a common vertical-integration pattern in the target market.

Key Data Entities (SRS 4.16): CrusherProductionRecord, AsphaltPlantBatch,
ConcretePlantBatch, QuarryProductionRecord, Stockpile,
ExplosivesRegister, DrillingRecord, BlastingRecord, HaulageRecord,
ProductionReport.

Design notes:
  - `ExplosivesRegisterCorrection` is not in the SRS's named entity list
    but is the necessary mechanism for the business rule "cannot be
    deleted, only appended/corrected with an audit trail": a correction
    is its OWN row, linked back to the entry it corrects, never an
    UPDATE or DELETE against the original. services.py enforces this by
    simply never exposing an update/delete path for ExplosivesRegister
    at all -- the absence of that route is the enforcement.
  - Business rule (SRS 4.16): a Blasting Record requires a linked
    Drilling Record (enforced at the schema level -- drilling_record_id
    is NOT NULL) and, where the tenant's jurisdiction requires it, a
    recorded regulatory notification reference before the blast event
    can be marked complete (enforced in services.mark_blast_complete).
"""
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin


EXPLOSIVES_ENTRY_TYPES = ("procurement", "storage", "issuance", "consumption")
BLAST_STATUSES = ("planned", "completed")


class CrusherProductionRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PQ-01: per shift, input material, output gradation split, and
    downtime."""

    __tablename__ = "pq_crusher_production_records"

    plant_name = db.Column(db.String(128), nullable=False)
    shift_date = db.Column(db.Date, nullable=False)
    shift = db.Column(db.String(16), nullable=True)  # e.g. "day", "night"
    input_material = db.Column(db.String(128), nullable=True)
    input_quantity = db.Column(db.Numeric(14, 4), nullable=True)
    output_gradation = db.Column(JSONB, nullable=True)  # {"0-5mm": 100.0, "5-10mm": 200.0, ...}
    downtime_minutes = db.Column(db.Integer, nullable=False, default=0)
    downtime_reason = db.Column(db.Text, nullable=True)


class AsphaltPlantBatch(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PQ-02: mix design reference, temperature, quantity produced,
    linked to Module 13 lab results (loose reference)."""

    __tablename__ = "pq_asphalt_plant_batches"

    plant_name = db.Column(db.String(128), nullable=False)
    mix_design_reference = db.Column(db.String(128), nullable=True)
    batch_date = db.Column(db.DateTime(timezone=True), nullable=True)
    temperature = db.Column(db.Numeric(6, 2), nullable=True)
    quantity_produced = db.Column(db.Numeric(14, 4), nullable=True)
    unit = db.Column(db.String(16), nullable=True)
    lab_result_id = db.Column(UUID(as_uuid=True), nullable=True)  # qms_lab_results.id, loose reference


class ConcretePlantBatch(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PQ-03: batch weights, water/cement ratio, destination pour
    (Module 6, loose reference)."""

    __tablename__ = "pq_concrete_plant_batches"

    plant_name = db.Column(db.String(128), nullable=False)
    mix_design_reference = db.Column(db.String(128), nullable=True)
    batch_date = db.Column(db.DateTime(timezone=True), nullable=True)
    batch_weights = db.Column(JSONB, nullable=True)  # {"cement": 350, "sand": 700, "aggregate": 1100, "water": 175}
    water_cement_ratio = db.Column(db.Numeric(5, 3), nullable=True)
    quantity_produced = db.Column(db.Numeric(14, 4), nullable=True)
    destination_pour_reference = db.Column(UUID(as_uuid=True), nullable=True)  # exe_concrete_pour_records.id, loose


class QuarryProductionRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PQ-04: by face/bench, material type, volume extracted."""

    __tablename__ = "pq_quarry_production_records"

    quarry_name = db.Column(db.String(128), nullable=False)
    face_or_bench = db.Column(db.String(128), nullable=True)
    material_type = db.Column(db.String(128), nullable=True)
    volume_extracted = db.Column(db.Numeric(14, 4), nullable=True)
    production_date = db.Column(db.Date, nullable=True)


class Stockpile(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PQ-05: quantity and location by material type, reconciled
    against Module 8 receipts (loose reference, caller-supplied)."""

    __tablename__ = "pq_stockpiles"

    material_type = db.Column(db.String(128), nullable=False)
    location = db.Column(db.String(255), nullable=True)
    quantity = db.Column(db.Numeric(14, 4), nullable=False, default=0)
    last_reconciled_at = db.Column(db.DateTime(timezone=True), nullable=True)


class ExplosivesRegister(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PQ-06: business rule -- cannot be deleted, only
    appended/corrected with an audit trail. No update/delete route
    exists for this model anywhere in routes.py; corrections are
    ExplosivesRegisterCorrection rows instead."""

    __tablename__ = "pq_explosives_register"

    entry_type = db.Column(db.String(16), nullable=False)
    material_type = db.Column(db.String(128), nullable=False)  # e.g. "ANFO", "detonators", "boosters"
    quantity = db.Column(db.Numeric(14, 4), nullable=False)
    unit = db.Column(db.String(32), nullable=True)
    entry_date = db.Column(db.DateTime(timezone=True), nullable=True)
    reference_number = db.Column(db.String(128), nullable=True)
    recorded_by = db.Column(UUID(as_uuid=True), nullable=True)

    corrections = relationship("ExplosivesRegisterCorrection", back_populates="entry")

    __table_args__ = (db.CheckConstraint(f"entry_type IN {EXPLOSIVES_ENTRY_TYPES}", name="ck_pq_explosives_entry_type"),)


class ExplosivesRegisterCorrection(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """The sanctioned correction mechanism for an ExplosivesRegister
    entry -- a new, separate, attributable row, never a mutation of the
    original."""

    __tablename__ = "pq_explosives_register_corrections"

    entry_id = db.Column(UUID(as_uuid=True), db.ForeignKey("pq_explosives_register.id"), nullable=False, index=True)
    reason = db.Column(db.Text, nullable=False)
    corrected_quantity = db.Column(db.Numeric(14, 4), nullable=True)
    corrected_by = db.Column(UUID(as_uuid=True), nullable=True)
    corrected_at = db.Column(db.DateTime(timezone=True), nullable=True)

    entry = relationship("ExplosivesRegister", back_populates="corrections")


class DrillingRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PQ-07: pattern, depth, hole count, preceding a blast event."""

    __tablename__ = "pq_drilling_records"

    quarry_name = db.Column(db.String(128), nullable=False)
    pattern_reference = db.Column(db.String(128), nullable=True)
    hole_count = db.Column(db.Integer, nullable=True)
    depth = db.Column(db.Numeric(8, 2), nullable=True)
    drilled_at = db.Column(db.DateTime(timezone=True), nullable=True)

    blasts = relationship("BlastingRecord", back_populates="drilling_record")


class BlastingRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PQ-08: business rule -- requires a linked Drilling Record
    (enforced by drilling_record_id being NOT NULL) and, where required,
    a recorded regulatory notification reference before the blast can
    be marked complete (services.mark_blast_complete)."""

    __tablename__ = "pq_blasting_records"

    drilling_record_id = db.Column(UUID(as_uuid=True), db.ForeignKey("pq_drilling_records.id"), nullable=False, index=True)

    explosives_used = db.Column(JSONB, nullable=True)  # [{material_type, quantity, unit}, ...]
    blast_design = db.Column(db.Text, nullable=True)
    vibration_monitoring_result = db.Column(db.Numeric(10, 4), nullable=True)
    fly_rock_monitoring_result = db.Column(db.Text, nullable=True)
    regulatory_notification_reference = db.Column(db.String(128), nullable=True)
    blast_date = db.Column(db.DateTime(timezone=True), nullable=True)
    status = db.Column(db.String(16), nullable=False, default="planned")

    drilling_record = relationship("DrillingRecord", back_populates="blasts")

    __table_args__ = (db.CheckConstraint(f"status IN {BLAST_STATUSES}", name="ck_pq_blasting_status"),)


class HaulageRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PQ-09: loads, tonnage, cycle time, between quarry/plant and
    site/stockpile."""

    __tablename__ = "pq_haulage_records"

    source = db.Column(db.String(128), nullable=True)
    destination = db.Column(db.String(128), nullable=True)
    load_count = db.Column(db.Integer, nullable=True)
    tonnage = db.Column(db.Numeric(14, 4), nullable=True)
    cycle_time_minutes = db.Column(db.Integer, nullable=True)
    haul_date = db.Column(db.Date, nullable=True)


class ProductionReport(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PQ-10: consolidated by plant/quarry/period, including yield
    efficiency and cost per ton/m3 produced. Stored (not purely
    computed-on-read) because a generated report is itself a
    reportable, referenceable record -- same reasoning as FUEL's
    FuelVarianceRecord."""

    __tablename__ = "pq_production_reports"

    plant_or_quarry_name = db.Column(db.String(128), nullable=False)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    total_output = db.Column(db.Numeric(14, 4), nullable=True)
    yield_efficiency_pct = db.Column(db.Numeric(5, 2), nullable=True)
    cost_per_unit = db.Column(db.Numeric(14, 4), nullable=True)
    generated_at = db.Column(db.DateTime(timezone=True), nullable=True)
