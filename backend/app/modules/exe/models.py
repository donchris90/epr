"""
Module 6 — Project Execution (Code: EXE)
SRS Section 4.6.

The daily operating record of the project -- what actually happened on
site -- captured primarily through the offline-first Mobile Field App
(Module 24) but fully manageable from the web.

Key Data Entities (SRS 4.6): DailySiteDiary, DailyReport, SitePhoto,
SiteVideo, WeatherRecord, ProgressEntry, WorkCompletedRecord,
SiteIssue, VisitorLog, EquipmentUsageRecord, LaborUsageRecord,
ConcretePourRecord, InspectionLog.

Design notes:
  - SitePhoto and SiteVideo share an identical shape (a Document
    reference plus geotag/timestamp metadata), so they're one table,
    `SiteMedia`, discriminated by `media_type` -- the same pattern used
    for EST's ContingencyItem (contingency vs. risk allowance).
  - `activity_id` fields are loose references to app.modules.pln's
    Activity (no FK) -- EXE reads that ID for progress tracking and
    display but never queries pln_* tables directly (bounded-context
    discipline, SRS 3.3). Same for `boq_item_id` (Module 2/3's BOQ
    items) and `itp_reference` (Module 13's Inspection & Test Plan,
    not yet built).
  - WorkCompletedRecord's "cannot exceed contracted quantity" business
    rule (SRS 4.6) is a WARNING, not a hard block, per the SRS's own
    wording -- and since EXE doesn't own contract BOQ quantities, the
    caller supplies `contracted_quantity` explicitly (see services.py).
"""
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin


DIARY_STATUSES = ("draft", "signed")
MEDIA_TYPES = ("photo", "video")
PROGRESS_MEASUREMENT_TYPES = ("percentage", "quantity")
ISSUE_SEVERITIES = ("low", "medium", "high", "critical")
ISSUE_STATUSES = ("open", "in_progress", "resolved", "escalated")
INSPECTION_OUTCOMES = ("pass", "fail", "conditional")


class DailySiteDiary(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EXE-01, EXE-12: one diary per project per day. Business rule:
    once signed, becomes read-only -- see services.update_diary /
    services.amend_diary."""

    __tablename__ = "exe_daily_site_diaries"

    project_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    diary_date = db.Column(db.Date, nullable=False, index=True)

    workforce_present_count = db.Column(db.Integer, nullable=True)
    equipment_on_site_summary = db.Column(db.Text, nullable=True)
    narrative = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(16), nullable=False, default="draft")
    signed_by = db.Column(UUID(as_uuid=True), nullable=True)
    signed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    countersigned_by = db.Column(UUID(as_uuid=True), nullable=True)
    countersigned_at = db.Column(db.DateTime(timezone=True), nullable=True)

    weather_records = relationship("WeatherRecord", back_populates="diary", cascade="all, delete-orphan")
    amendments = relationship("DiaryAmendment", back_populates="diary", cascade="all, delete-orphan")

    __table_args__ = (
        db.CheckConstraint(f"status IN {DIARY_STATUSES}", name="ck_exe_diaries_status"),
        db.UniqueConstraint("tenant_id", "project_id", "diary_date", name="uq_exe_diaries_project_date"),
    )


class DiaryAmendment(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """The ONLY sanctioned way to correct a signed diary's content (SRS
    4.6 business rule) -- a logged addendum, never an edit to signed
    content."""

    __tablename__ = "exe_diary_amendments"

    diary_id = db.Column(UUID(as_uuid=True), db.ForeignKey("exe_daily_site_diaries.id"), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    amended_by = db.Column(UUID(as_uuid=True), nullable=True)

    diary = relationship("DailySiteDiary", back_populates="amendments")


class DailyReport(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EXE-02: a generated, shareable compilation of a diary's data
    (diary + photos + progress + issues) into a PDF. The generation
    itself is a Celery task (see app/celery_app.py); this row tracks
    the resulting document."""

    __tablename__ = "exe_daily_reports"

    diary_id = db.Column(UUID(as_uuid=True), db.ForeignKey("exe_daily_site_diaries.id"), nullable=False, index=True)
    document_id = db.Column(UUID(as_uuid=True), db.ForeignKey("documents.id"), nullable=True)
    generated_at = db.Column(db.DateTime(timezone=True), nullable=True)


class SiteMedia(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EXE-03: photos and videos attached to a diary, activity, or
    inspection record, with geotag/timestamp metadata."""

    __tablename__ = "exe_site_media"

    document_id = db.Column(UUID(as_uuid=True), db.ForeignKey("documents.id"), nullable=False)
    media_type = db.Column(db.String(8), nullable=False)

    diary_id = db.Column(UUID(as_uuid=True), db.ForeignKey("exe_daily_site_diaries.id"), nullable=True, index=True)
    activity_id = db.Column(UUID(as_uuid=True), nullable=True)  # pln_activities.id, loose reference
    inspection_log_id = db.Column(UUID(as_uuid=True), db.ForeignKey("exe_inspection_logs.id"), nullable=True)

    latitude = db.Column(db.Numeric(9, 6), nullable=True)
    longitude = db.Column(db.Numeric(9, 6), nullable=True)
    captured_at = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (db.CheckConstraint(f"media_type IN {MEDIA_TYPES}", name="ck_exe_site_media_type"),)


class WeatherRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EXE-04: weather conditions for delay-claim substantiation."""

    __tablename__ = "exe_weather_records"

    diary_id = db.Column(UUID(as_uuid=True), db.ForeignKey("exe_daily_site_diaries.id"), nullable=False, index=True)
    recorded_at = db.Column(db.DateTime(timezone=True), nullable=True)
    condition = db.Column(db.String(64), nullable=True)  # e.g. "sunny", "heavy_rain"
    temperature_c = db.Column(db.Numeric(4, 1), nullable=True)
    rainfall_mm = db.Column(db.Numeric(6, 1), nullable=True)
    wind_kph = db.Column(db.Numeric(5, 1), nullable=True)
    source = db.Column(db.String(16), nullable=False, default="manual")  # manual | api

    diary = relationship("DailySiteDiary", back_populates="weather_records")


class ProgressEntry(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EXE-05: progress against a WBS activity, feeding Module 19's
    earned value calculation."""

    __tablename__ = "exe_progress_entries"

    diary_id = db.Column(UUID(as_uuid=True), db.ForeignKey("exe_daily_site_diaries.id"), nullable=True, index=True)
    activity_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)  # pln_activities.id, loose reference

    measurement_type = db.Column(db.String(16), nullable=False)
    value = db.Column(db.Numeric(12, 4), nullable=False)
    unit = db.Column(db.String(32), nullable=True)
    recorded_at = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        db.CheckConstraint(f"measurement_type IN {PROGRESS_MEASUREMENT_TYPES}", name="ck_exe_progress_entries_type"),
    )


class WorkCompletedRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EXE-06: quantities of BOQ items completed, cross-referenced to
    measurement sheets (Module 12) and billing (Module 18) once those
    exist. Business rule: cumulative completed quantity cannot exceed
    the contracted quantity without a linked Variation Order --
    enforced as a WARNING flag, not a hard block, per the SRS's own
    wording (see services.record_work_completed)."""

    __tablename__ = "exe_work_completed_records"

    diary_id = db.Column(UUID(as_uuid=True), db.ForeignKey("exe_daily_site_diaries.id"), nullable=True, index=True)
    boq_item_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)  # loose reference, see module docstring

    quantity = db.Column(db.Numeric(18, 4), nullable=False)
    unit = db.Column(db.String(32), nullable=True)
    recorded_at = db.Column(db.DateTime(timezone=True), nullable=True)

    variation_order_id = db.Column(UUID(as_uuid=True), nullable=True)  # Module 18, once it exists
    exceeds_contracted_quantity = db.Column(db.Boolean, nullable=False, default=False)


class SiteIssue(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EXE-07: site issues with severity, ownership, and escalation."""

    __tablename__ = "exe_site_issues"

    project_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    diary_id = db.Column(UUID(as_uuid=True), db.ForeignKey("exe_daily_site_diaries.id"), nullable=True, index=True)

    category = db.Column(db.String(64), nullable=True)
    severity = db.Column(db.String(16), nullable=False, default="medium")
    description = db.Column(db.Text, nullable=False)
    assigned_owner_id = db.Column(UUID(as_uuid=True), nullable=True)
    status = db.Column(db.String(16), nullable=False, default="open", index=True)

    due_date = db.Column(db.Date, nullable=True)
    resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    escalated_at = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        db.CheckConstraint(f"severity IN {ISSUE_SEVERITIES}", name="ck_exe_site_issues_severity"),
        db.CheckConstraint(f"status IN {ISSUE_STATUSES}", name="ck_exe_site_issues_status"),
    )


class VisitorLog(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EXE-08: site access records supporting HSE induction
    verification."""

    __tablename__ = "exe_visitor_logs"

    project_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    diary_id = db.Column(UUID(as_uuid=True), db.ForeignKey("exe_daily_site_diaries.id"), nullable=True, index=True)

    visitor_name = db.Column(db.String(255), nullable=False)
    company = db.Column(db.String(255), nullable=True)
    purpose = db.Column(db.String(255), nullable=True)
    hse_induction_verified = db.Column(db.Boolean, nullable=False, default=False)
    signed_in_at = db.Column(db.DateTime(timezone=True), nullable=True)
    signed_out_at = db.Column(db.DateTime(timezone=True), nullable=True)


class EquipmentUsageRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EXE-09: equipment used per day per activity, feeding Module 9
    (Equipment & Fleet) for utilization tracking."""

    __tablename__ = "exe_equipment_usage_records"

    diary_id = db.Column(UUID(as_uuid=True), db.ForeignKey("exe_daily_site_diaries.id"), nullable=False, index=True)
    activity_id = db.Column(UUID(as_uuid=True), nullable=True)  # pln_activities.id, loose reference

    equipment_identifier = db.Column(db.String(128), nullable=False)  # asset tag or name
    hours_used = db.Column(db.Numeric(5, 2), nullable=False)
    fuel_used_litres = db.Column(db.Numeric(8, 2), nullable=True)
    operator_name = db.Column(db.String(255), nullable=True)


class LaborUsageRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EXE-09: labor used per day per activity, feeding Module 11
    (Workforce Management) for cost allocation."""

    __tablename__ = "exe_labor_usage_records"

    diary_id = db.Column(UUID(as_uuid=True), db.ForeignKey("exe_daily_site_diaries.id"), nullable=False, index=True)
    activity_id = db.Column(UUID(as_uuid=True), nullable=True)  # pln_activities.id, loose reference

    trade = db.Column(db.String(128), nullable=False)
    headcount = db.Column(db.Integer, nullable=False)
    hours_worked = db.Column(db.Numeric(5, 2), nullable=False)


class ConcretePourRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EXE-10: structured concrete pour records linked to QMS
    inspection records (Module 13, via inspection_log_id here in the
    interim since Module 13's ITP records don't exist yet)."""

    __tablename__ = "exe_concrete_pour_records"

    diary_id = db.Column(UUID(as_uuid=True), db.ForeignKey("exe_daily_site_diaries.id"), nullable=True, index=True)
    activity_id = db.Column(UUID(as_uuid=True), nullable=True)  # pln_activities.id, loose reference
    inspection_log_id = db.Column(UUID(as_uuid=True), db.ForeignKey("exe_inspection_logs.id"), nullable=True)

    mix_design = db.Column(db.String(255), nullable=True)
    volume_m3 = db.Column(db.Numeric(8, 2), nullable=False)
    slump_mm = db.Column(db.Numeric(5, 1), nullable=True)
    cube_references = db.Column(JSONB, nullable=True)  # list of cube/sample reference strings
    weather_at_pour = db.Column(db.String(64), nullable=True)
    pour_started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    pour_completed_at = db.Column(db.DateTime(timezone=True), nullable=True)


class InspectionLog(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EXE-11: inspection records referencing an Inspection & Test Plan
    (Module 13, not yet built -- `itp_reference` is a loose text
    reference until that module exists to link against properly)."""

    __tablename__ = "exe_inspection_logs"

    diary_id = db.Column(UUID(as_uuid=True), db.ForeignKey("exe_daily_site_diaries.id"), nullable=True, index=True)
    itp_reference = db.Column(db.String(128), nullable=True)

    inspected_item = db.Column(db.String(255), nullable=False)
    outcome = db.Column(db.String(16), nullable=False)
    inspector_name = db.Column(db.String(255), nullable=True)
    inspected_at = db.Column(db.DateTime(timezone=True), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    __table_args__ = (db.CheckConstraint(f"outcome IN {INSPECTION_OUTCOMES}", name="ck_exe_inspection_logs_outcome"),)
