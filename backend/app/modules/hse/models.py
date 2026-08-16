"""
Module 14 — Health, Safety & Environment (HSE) (Code: HSE)
SRS Section 4.14.

The permit, incident, and audit trail that keeps a contracting business
insurable, certifiable, and -- most importantly -- its workforce safe.

Key Data Entities (SRS 4.14): PermitToWork, Incident, NearMiss,
ToolboxTalk, PPERecord, SafetyAudit, RiskAssessment,
EnvironmentalMonitoringRecord, WasteDisposalRecord,
EmergencyResponsePlan.

Design notes:
  - `ToolboxTalkAttendee` is not in the SRS's named entity list but is
    the necessary join table for HSE-04's "attendee list (linked to
    Module 11 employee/casual worker records)" -- a talk needs multiple
    attendees, each a loose reference to a wfm_employees or
    wfm_casual_workers row (bounded-context discipline, SRS 3.3).
  - Business rule (SRS 4.14): a Permit to Work must be FORMALLY closed
    (not merely time-expired) before associated work is marked complete
    in Module 6 -- `formally_closed` is a distinct boolean from
    `valid_until` passing, and services.close_permit is the only path
    that sets it.
  - Business rule (SRS 4.14): every recordable Incident automatically
    generates a Corrective Action requirement -- via a call into
    Module 13's service (app.modules.qms.services), not a duplicated
    table. QMS's CorrectiveAction.source now includes "incident"
    (extended in this same change) specifically to support this.
  - HSE-12's block on Permit to Work issuance if the worker's safety
    training isn't current takes that fact as a caller-supplied
    parameter (`workers_training_current`) rather than HSE querying
    Module 11's tables directly -- the same pattern used throughout
    (EXE's contracted_quantity, PRC's remaining_budget, EQP's
    fuel_normal_cost).
"""
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin


PERMIT_TYPES = ("hot_work", "confined_space", "excavation", "working_at_height")
PERMIT_STATUSES = ("draft", "approved", "active", "closed")
INCIDENT_CLASSIFICATIONS = ("first_aid", "medical_treatment", "lost_time", "fatality")
INCIDENT_STATUSES = ("open", "closed")
SAFETY_AUDIT_TYPES = ("scheduled", "ad_hoc")
RISK_ASSESSMENT_STATUSES = ("active", "expired", "superseded")
ENV_MONITORING_TYPES = ("dust", "noise", "water_discharge")
WASTE_TYPES = ("construction", "hazardous")


class RiskAssessment(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """HSE-07: per activity/area, requiring review and re-approval on a
    configurable interval. Referenced by PermitToWork for the HSE-12
    gate."""

    __tablename__ = "hse_risk_assessments"

    project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)
    activity_or_area = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    risk_level = db.Column(db.String(16), nullable=True)  # e.g. "low", "medium", "high"
    status = db.Column(db.String(16), nullable=False, default="active")
    approved_by = db.Column(UUID(as_uuid=True), nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    valid_until = db.Column(db.Date, nullable=True, index=True)
    review_interval_days = db.Column(db.Integer, nullable=True)

    permits = relationship("PermitToWork", back_populates="risk_assessment")

    __table_args__ = (db.CheckConstraint(f"status IN {RISK_ASSESSMENT_STATUSES}", name="ck_hse_risk_status"),)


class PermitToWork(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """HSE-01: business rule -- must be FORMALLY closed (not merely
    time-expired) before associated work is marked complete elsewhere.
    Also gated by HSE-12: cannot issue if the linked Risk Assessment is
    expired or workers' safety training isn't current."""

    __tablename__ = "hse_permits_to_work"

    project_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    risk_assessment_id = db.Column(UUID(as_uuid=True), db.ForeignKey("hse_risk_assessments.id"), nullable=True)

    permit_type = db.Column(db.String(24), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="draft", index=True)

    approved_by = db.Column(UUID(as_uuid=True), nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    issued_at = db.Column(db.DateTime(timezone=True), nullable=True)
    valid_until = db.Column(db.DateTime(timezone=True), nullable=True)

    formally_closed = db.Column(db.Boolean, nullable=False, default=False)
    closed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    closed_by = db.Column(UUID(as_uuid=True), nullable=True)

    risk_assessment = relationship("RiskAssessment", back_populates="permits")

    __table_args__ = (
        db.CheckConstraint(f"permit_type IN {PERMIT_TYPES}", name="ck_hse_permits_type"),
        db.CheckConstraint(f"status IN {PERMIT_STATUSES}", name="ck_hse_permits_status"),
    )


class Incident(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """HSE-02: business rule -- every recordable incident automatically
    generates a linked Corrective Action (Module 13) -- see
    services.record_incident."""

    __tablename__ = "hse_incidents"

    project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)
    classification = db.Column(db.String(24), nullable=False)
    description = db.Column(db.Text, nullable=False)
    investigation_findings = db.Column(db.Text, nullable=True)
    regulatory_reportable = db.Column(db.Boolean, nullable=False, default=False)

    occurred_at = db.Column(db.DateTime(timezone=True), nullable=True)
    reported_by = db.Column(UUID(as_uuid=True), nullable=True)
    status = db.Column(db.String(16), nullable=False, default="open")

    corrective_action_id = db.Column(UUID(as_uuid=True), nullable=True)  # qms_corrective_actions.id, loose reference

    __table_args__ = (
        db.CheckConstraint(f"classification IN {INCIDENT_CLASSIFICATIONS}", name="ck_hse_incidents_classification"),
        db.CheckConstraint(f"status IN {INCIDENT_STATUSES}", name="ck_hse_incidents_status"),
    )


class NearMiss(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """HSE-03: same structured classification as Incident, distinguished
    by outcome severity -- feeds leading-indicator safety metrics."""

    __tablename__ = "hse_near_misses"

    project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)
    classification = db.Column(db.String(24), nullable=False)
    description = db.Column(db.Text, nullable=False)
    occurred_at = db.Column(db.DateTime(timezone=True), nullable=True)
    reported_by = db.Column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        db.CheckConstraint(f"classification IN {INCIDENT_CLASSIFICATIONS}", name="ck_hse_near_misses_classification"),
    )


class ToolboxTalk(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """HSE-04: topic, facilitator, and attendee list (see
    ToolboxTalkAttendee)."""

    __tablename__ = "hse_toolbox_talks"

    project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)
    topic = db.Column(db.String(255), nullable=False)
    facilitator_id = db.Column(UUID(as_uuid=True), nullable=True)
    held_at = db.Column(db.DateTime(timezone=True), nullable=True)
    facilitator_signed = db.Column(db.Boolean, nullable=False, default=False)

    attendees = relationship("ToolboxTalkAttendee", back_populates="talk", cascade="all, delete-orphan")


class ToolboxTalkAttendee(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    __tablename__ = "hse_toolbox_talk_attendees"

    talk_id = db.Column(UUID(as_uuid=True), db.ForeignKey("hse_toolbox_talks.id"), nullable=False, index=True)
    employee_id = db.Column(UUID(as_uuid=True), nullable=True)  # wfm_employees.id, loose reference
    casual_worker_id = db.Column(UUID(as_uuid=True), nullable=True)  # wfm_casual_workers.id, loose reference

    talk = relationship("ToolboxTalk", back_populates="attendees")

    __table_args__ = (
        db.CheckConstraint(
            "(employee_id IS NOT NULL AND casual_worker_id IS NULL) OR "
            "(employee_id IS NULL AND casual_worker_id IS NOT NULL)",
            name="ck_hse_talk_attendees_exactly_one_worker",
        ),
    )


class PPERecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """HSE-05: PPE issuance per worker, cross-referenced to Module 8
    stock (loose reference) for reorder alerting."""

    __tablename__ = "hse_ppe_records"

    employee_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)
    casual_worker_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)
    material_item_id = db.Column(UUID(as_uuid=True), nullable=True)  # inv_material_items.id, loose reference

    ppe_type = db.Column(db.String(128), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    issued_at = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        db.CheckConstraint(
            "(employee_id IS NOT NULL AND casual_worker_id IS NULL) OR "
            "(employee_id IS NULL AND casual_worker_id IS NOT NULL)",
            name="ck_hse_ppe_records_exactly_one_worker",
        ),
    )


class SafetyAudit(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """HSE-06: scheduled or ad hoc, configurable checklist, with
    corrective-action linkage to Module 13 (loose reference)."""

    __tablename__ = "hse_safety_audits"

    project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)
    audit_type = db.Column(db.String(16), nullable=False, default="scheduled")
    checklist = db.Column(JSONB, nullable=True)  # [{item, result, notes}, ...]
    score = db.Column(db.Numeric(5, 2), nullable=True)
    audit_date = db.Column(db.Date, nullable=True)
    auditor_id = db.Column(UUID(as_uuid=True), nullable=True)
    corrective_action_id = db.Column(UUID(as_uuid=True), nullable=True)  # qms_corrective_actions.id, loose reference

    __table_args__ = (db.CheckConstraint(f"audit_type IN {SAFETY_AUDIT_TYPES}", name="ck_hse_audits_type"),)


class EnvironmentalMonitoringRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """HSE-08: dust, noise, water discharge quality, where required by
    project environmental permits."""

    __tablename__ = "hse_environmental_monitoring_records"

    project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)
    monitoring_type = db.Column(db.String(16), nullable=False)
    recorded_at = db.Column(db.DateTime(timezone=True), nullable=True)
    value = db.Column(db.Numeric(12, 4), nullable=True)
    unit = db.Column(db.String(32), nullable=True)
    threshold = db.Column(db.Numeric(12, 4), nullable=True)
    exceeds_threshold = db.Column(db.Boolean, nullable=False, default=False)

    __table_args__ = (db.CheckConstraint(f"monitoring_type IN {ENV_MONITORING_TYPES}", name="ck_hse_env_monitoring_type"),)


class WasteDisposalRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """HSE-09: manifest/certificate of disposal attachment for
    regulatory compliance."""

    __tablename__ = "hse_waste_disposal_records"

    project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)
    waste_type = db.Column(db.String(16), nullable=False)
    quantity = db.Column(db.Numeric(12, 4), nullable=True)
    unit = db.Column(db.String(32), nullable=True)
    disposed_at = db.Column(db.Date, nullable=True)
    manifest_document_id = db.Column(UUID(as_uuid=True), db.ForeignKey("documents.id"), nullable=True)
    disposal_certificate_document_id = db.Column(UUID(as_uuid=True), db.ForeignKey("documents.id"), nullable=True)

    __table_args__ = (db.CheckConstraint(f"waste_type IN {WASTE_TYPES}", name="ck_hse_waste_type"),)


class EmergencyResponsePlan(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """HSE-10: per project/site, designed to be accessible offline from
    the Mobile Field App (a sync/caching concern for Module 24, not
    modeled here -- this table is just the source of truth)."""

    __tablename__ = "hse_emergency_response_plans"

    project_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    muster_points = db.Column(JSONB, nullable=True)  # [{name, latitude, longitude}, ...]
    emergency_contacts = db.Column(JSONB, nullable=True)  # [{role, name, phone}, ...]
    designated_roles = db.Column(JSONB, nullable=True)  # [{role, employee_id}, ...]
    version = db.Column(db.Integer, nullable=False, default=1)
    effective_from = db.Column(db.Date, nullable=True)
