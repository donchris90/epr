"""
Module 13 — Quality Management (QMS) (Code: QMS)
SRS Section 4.13.

The auditable quality trail construction contracts and client
consultants require: planned inspections through to formal close-out.

Key Data Entities (SRS 4.13): InspectionTestPlan, MaterialApproval,
LabResult, NCR, PunchListItem, CorrectiveAction, SnagListItem.

Design notes:
  - `ITPHoldPoint` is not in the SRS's named entity list but is what
    makes InspectionTestPlan real -- QMS-01 requires "hold points,
    checks, and acceptance criteria," and the first business rule
    (work cannot proceed past a hold point without a pass or approved
    concession) needs somewhere to actually gate. QMS-09's link to
    Module 6's InspectionLog is a loose reference in the other
    direction: EXE's InspectionLog.itp_reference (a plain string field,
    since QMS didn't exist when Module 6 was built) is where a hold
    point's ID should be recorded by convention once both modules are
    wired together by a caller -- QMS does not modify EXE's schema
    retroactively.
  - PunchListItem and SnagListItem are DELIBERATELY kept as separate
    tables with near-identical shape, unlike other pairs consolidated
    elsewhere in this codebase (e.g. EXE's SiteMedia, EST's
    ContingencyItem). QMS-07 explicitly wants them distinguishable per
    tenant/contract terminology -- consolidating them into one
    discriminated table would work against that requirement, not just
    be untidy.
"""
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin


ITP_STATUSES = ("active", "archived")
HOLD_POINT_STATUSES = ("pending", "passed", "failed", "concession_approved")
MATERIAL_APPROVAL_STATUSES = ("submitted", "approved", "rejected")
LAB_TEST_TYPES = ("concrete_cube_strength", "compaction_density", "asphalt_extraction", "other")
NCR_DISPOSITIONS = ("rework", "accept_as_is", "reject")
NCR_STATUSES = ("open", "closed")
CORRECTIVE_ACTION_SOURCES = ("ncr", "audit", "incident")
CORRECTIVE_ACTION_STATUSES = ("open", "completed", "verified")
PUNCH_LIST_STATUSES = ("open", "closed")
SNAG_LIST_STATUSES = ("open", "closed")


class InspectionTestPlan(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """QMS-01: defined per work activity type, specifying required hold
    points, checks, and acceptance criteria."""

    __tablename__ = "qms_itps"

    project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)
    activity_type = db.Column(db.String(128), nullable=False)  # e.g. "concrete_pour", "structural_steel_erection"
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="active")

    hold_points = relationship(
        "ITPHoldPoint", back_populates="itp", order_by="ITPHoldPoint.sequence_order", cascade="all, delete-orphan"
    )

    __table_args__ = (db.CheckConstraint(f"status IN {ITP_STATUSES}", name="ck_qms_itps_status"),)


class ITPHoldPoint(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """Business rule (SRS 4.13): work may not proceed past a hold point
    marked `is_mandatory_hold` without a recorded pass or an approved
    concession -- enforced in services.check_can_proceed, a workflow
    gate other modules/routes should call before letting work continue,
    not a passive reminder."""

    __tablename__ = "qms_itp_hold_points"

    itp_id = db.Column(UUID(as_uuid=True), db.ForeignKey("qms_itps.id"), nullable=False, index=True)
    sequence_order = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=False)
    required_check = db.Column(db.Text, nullable=True)
    acceptance_criteria = db.Column(db.Text, nullable=True)
    is_mandatory_hold = db.Column(db.Boolean, nullable=False, default=True)

    status = db.Column(db.String(24), nullable=False, default="pending")
    inspection_log_id = db.Column(UUID(as_uuid=True), nullable=True)  # exe_inspection_logs.id, loose reference (QMS-09)
    result_recorded_by = db.Column(UUID(as_uuid=True), nullable=True)
    result_recorded_at = db.Column(db.DateTime(timezone=True), nullable=True)

    concession_reason = db.Column(db.Text, nullable=True)
    concession_approved_by = db.Column(UUID(as_uuid=True), nullable=True)
    concession_approved_at = db.Column(db.DateTime(timezone=True), nullable=True)

    itp = relationship("InspectionTestPlan", back_populates="hold_points")

    __table_args__ = (
        db.CheckConstraint(f"status IN {HOLD_POINT_STATUSES}", name="ck_qms_hold_points_status"),
        db.UniqueConstraint("itp_id", "sequence_order", name="uq_qms_hold_points_itp_order"),
    )


class MaterialApproval(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """QMS-02: submittal with a client/consultant approval workflow
    before the material may be used, cross-referenced to Module 8
    stock (loose reference)."""

    __tablename__ = "qms_material_approvals"

    material_item_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)  # inv_material_items.id
    submittal_reference = db.Column(db.String(128), nullable=False)
    technical_data_document_id = db.Column(UUID(as_uuid=True), db.ForeignKey("documents.id"), nullable=True)

    status = db.Column(db.String(16), nullable=False, default="submitted")
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    reviewed_by = db.Column(db.String(255), nullable=True)  # often an external client/consultant name
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    review_notes = db.Column(db.Text, nullable=True)

    __table_args__ = (db.CheckConstraint(f"status IN {MATERIAL_APPROVAL_STATUSES}", name="ck_qms_material_approvals_status"),)


class LabResult(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """QMS-03: linked to the relevant pour/lot record (loose reference
    to Module 6's ConcretePourRecord or another lot identifier)."""

    __tablename__ = "qms_lab_results"

    pour_or_lot_reference = db.Column(UUID(as_uuid=True), nullable=True, index=True)  # exe_concrete_pour_records.id, loose
    test_type = db.Column(db.String(32), nullable=False)
    sample_reference = db.Column(db.String(128), nullable=True)
    tested_at = db.Column(db.Date, nullable=True)
    result_value = db.Column(db.Numeric(12, 4), nullable=True)
    unit = db.Column(db.String(32), nullable=True)
    acceptance_threshold = db.Column(db.Numeric(12, 4), nullable=True)
    pass_fail = db.Column(db.Boolean, nullable=True)  # null until determined
    lab_name = db.Column(db.String(255), nullable=True)

    __table_args__ = (db.CheckConstraint(f"test_type IN {LAB_TEST_TYPES}", name="ck_qms_lab_results_test_type"),)


class NCR(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """QMS-04: Non-Conformance Report. Business rule -- cannot be
    closed without a linked Corrective Action verified as complete
    (services.close_ncr)."""

    __tablename__ = "qms_ncrs"

    project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)
    description = db.Column(db.Text, nullable=False)
    photo_document_ids = db.Column(JSONB, nullable=True)  # list of documents.id, as strings
    root_cause = db.Column(db.Text, nullable=True)
    disposition = db.Column(db.String(16), nullable=True)  # null until decided
    status = db.Column(db.String(16), nullable=False, default="open", index=True)

    raised_by = db.Column(UUID(as_uuid=True), nullable=True)
    raised_at = db.Column(db.DateTime(timezone=True), nullable=True)
    closed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    corrective_actions = relationship("CorrectiveAction", back_populates="ncr")

    __table_args__ = (
        db.CheckConstraint(
            f"disposition IS NULL OR disposition IN {NCR_DISPOSITIONS}", name="ck_qms_ncrs_disposition"
        ),
        db.CheckConstraint(f"status IN {NCR_STATUSES}", name="ck_qms_ncrs_status"),
    )


class CorrectiveAction(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """QMS-06: arising from an NCR or a standalone audit, with owner,
    due date, and a distinct verification-of-closure step (completing
    the action and VERIFYING it are two different states -- see
    services.py)."""

    __tablename__ = "qms_corrective_actions"

    ncr_id = db.Column(UUID(as_uuid=True), db.ForeignKey("qms_ncrs.id"), nullable=True, index=True)
    source = db.Column(db.String(16), nullable=False, default="ncr")

    description = db.Column(db.Text, nullable=False)
    owner_id = db.Column(UUID(as_uuid=True), nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="open")

    verified_by = db.Column(UUID(as_uuid=True), nullable=True)
    verified_at = db.Column(db.DateTime(timezone=True), nullable=True)

    ncr = relationship("NCR", back_populates="corrective_actions")

    __table_args__ = (
        db.CheckConstraint(f"source IN {CORRECTIVE_ACTION_SOURCES}", name="ck_qms_corrective_actions_source"),
        db.CheckConstraint(f"status IN {CORRECTIVE_ACTION_STATUSES}", name="ck_qms_corrective_actions_status"),
    )


class PunchListItem(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """QMS-05: per area/building/section, tracked to closure before
    handover sign-off."""

    __tablename__ = "qms_punch_list_items"

    project_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    area_building_section = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="open", index=True)

    raised_at = db.Column(db.DateTime(timezone=True), nullable=True)
    closed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    closed_by = db.Column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (db.CheckConstraint(f"status IN {PUNCH_LIST_STATUSES}", name="ck_qms_punch_list_status"),)


class SnagListItem(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """QMS-07: deliberately a separate table from PunchListItem -- see
    module docstring."""

    __tablename__ = "qms_snag_list_items"

    project_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    area_building_section = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="open", index=True)

    raised_at = db.Column(db.DateTime(timezone=True), nullable=True)
    closed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    closed_by = db.Column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (db.CheckConstraint(f"status IN {SNAG_LIST_STATUSES}", name="ck_qms_snag_list_status"),)
