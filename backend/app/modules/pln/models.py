"""
Module 5 — Project Planning (Code: PLN)
SRS Section 4.5.

Full schedule engineering: WBS, dependency-driven scheduling with
critical-path calculation, resource loading, baselining, look-ahead
plans, and delay analysis.

Key Data Entities (SRS 4.5): WBSNode, Activity, ActivityDependency,
ResourceAssignment, Baseline, LookAheadPlan, DelayEvent.

Design notes:
  - `WBSNode.cbs_line_item_id` is the "linked to the CBS" requirement
    in PLN-01 -- a loose reference (no FK) to app.modules.est's
    CBSLineItem, consistent with bounded-context discipline: PLN reads
    that ID for display/traceability but never queries est_* tables.
  - CPM (critical-path method) fields on Activity --
    early_start/early_finish/late_start/late_finish/total_float_days/
    is_critical -- are DERIVED, recomputed by
    services.recalculate_schedule whenever an activity or dependency
    changes. They are stored (not computed on every read) because the
    Gantt chart (PLN-02) and Executive Dashboard need to query "which
    activities are critical" cheaply and often.
  - Baseline snapshots are immutable by construction: BaselineActivitySnapshot
    rows are written once at baseline-creation time and never updated
    (SRS 4.5 business rule: baselining does not get altered by later
    schedule changes; variance is always current-minus-baseline).
"""
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin


DEPENDENCY_TYPES = ("FS", "SS", "FF", "SF")  # Finish-to-Start, Start-to-Start, Finish-to-Finish, Start-to-Finish
RESOURCE_TYPES = ("labor", "equipment", "material")
LOOK_AHEAD_TYPES = ("two_week", "six_week")
DELAY_CAUSES = ("client", "contractor", "weather", "force_majeure")


class WBSNode(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PLN-01: hierarchical Work Breakdown Structure, linked to the CBS
    so schedule and cost share the same structural backbone."""

    __tablename__ = "pln_wbs_nodes"

    project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)  # projects.id
    parent_id = db.Column(UUID(as_uuid=True), db.ForeignKey("pln_wbs_nodes.id"), nullable=True, index=True)
    cbs_line_item_id = db.Column(UUID(as_uuid=True), nullable=True)  # est_cbs_line_items.id, traceability only

    code = db.Column(db.String(64), nullable=True)
    name = db.Column(db.String(255), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    activities = relationship("Activity", back_populates="wbs_node", cascade="all, delete-orphan")


class Activity(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PLN-02/03/04: a schedule activity. CPM fields are derived --
    see module docstring."""

    __tablename__ = "pln_activities"

    wbs_node_id = db.Column(UUID(as_uuid=True), db.ForeignKey("pln_wbs_nodes.id"), nullable=False, index=True)

    name = db.Column(db.String(255), nullable=False)
    planned_start = db.Column(db.Date, nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)
    percent_complete = db.Column(db.Numeric(5, 2), nullable=False, default=0)

    # Derived by services.recalculate_schedule (CPM forward/backward pass).
    early_start = db.Column(db.Date, nullable=True)
    early_finish = db.Column(db.Date, nullable=True)
    late_start = db.Column(db.Date, nullable=True)
    late_finish = db.Column(db.Date, nullable=True)
    total_float_days = db.Column(db.Integer, nullable=True)
    is_critical = db.Column(db.Boolean, nullable=False, default=False, index=True)

    wbs_node = relationship("WBSNode", back_populates="activities")
    resource_assignments = relationship("ResourceAssignment", back_populates="activity", cascade="all, delete-orphan")

    predecessor_links = relationship(
        "ActivityDependency",
        foreign_keys="ActivityDependency.successor_id",
        back_populates="successor",
        cascade="all, delete-orphan",
    )
    successor_links = relationship(
        "ActivityDependency",
        foreign_keys="ActivityDependency.predecessor_id",
        back_populates="predecessor",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.CheckConstraint("duration_days > 0", name="ck_pln_activities_duration_positive"),
        db.CheckConstraint(
            "percent_complete >= 0 AND percent_complete <= 100", name="ck_pln_activities_pct_range"
        ),
    )


class ActivityDependency(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PLN-04: FS/SS/FF/SF dependency with lag (positive) or lead
    (negative lag_days)."""

    __tablename__ = "pln_activity_dependencies"

    predecessor_id = db.Column(UUID(as_uuid=True), db.ForeignKey("pln_activities.id"), nullable=False, index=True)
    successor_id = db.Column(UUID(as_uuid=True), db.ForeignKey("pln_activities.id"), nullable=False, index=True)
    dependency_type = db.Column(db.String(2), nullable=False, default="FS")
    lag_days = db.Column(db.Integer, nullable=False, default=0)

    predecessor = relationship("Activity", foreign_keys=[predecessor_id], back_populates="successor_links")
    successor = relationship("Activity", foreign_keys=[successor_id], back_populates="predecessor_links")

    __table_args__ = (
        db.CheckConstraint(f"dependency_type IN {DEPENDENCY_TYPES}", name="ck_pln_activity_deps_type"),
        db.CheckConstraint("predecessor_id != successor_id", name="ck_pln_activity_deps_no_self_loop"),
        db.UniqueConstraint("predecessor_id", "successor_id", name="uq_pln_activity_deps_pair"),
    )


class ResourceAssignment(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PLN-05: labor/equipment/material assigned to an activity.
    Over-allocation is flagged by services.py, not stored here -- it's
    a derived read, not a fact about this row."""

    __tablename__ = "pln_resource_assignments"

    activity_id = db.Column(UUID(as_uuid=True), db.ForeignKey("pln_activities.id"), nullable=False, index=True)
    resource_type = db.Column(db.String(16), nullable=False)
    resource_name = db.Column(db.String(255), nullable=False, index=True)
    quantity = db.Column(db.Numeric(10, 2), nullable=False, default=1)
    unit = db.Column(db.String(32), nullable=True)

    activity = relationship("Activity", back_populates="resource_assignments")

    __table_args__ = (db.CheckConstraint(f"resource_type IN {RESOURCE_TYPES}", name="ck_pln_resource_assignments_type"),)


class Baseline(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PLN-06/PLN-11: an immutable schedule snapshot. `is_current` marks
    which baseline is authoritative for contractual EOT claims -- SRS
    requires "clear labeling", and only one may be current at a time
    (enforced in services.py, same pattern as EST's submitted
    EstimateVersion)."""

    __tablename__ = "pln_baselines"

    project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)
    label = db.Column(db.String(64), nullable=False)  # e.g. "original", "revised", "current"
    is_current = db.Column(db.Boolean, nullable=False, default=False)

    snapshots = relationship("BaselineActivitySnapshot", back_populates="baseline", cascade="all, delete-orphan")


class BaselineActivitySnapshot(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """Immutable per-activity snapshot at baseline-creation time. Never
    updated after creation -- that immutability is what makes variance
    (current minus baseline) meaningful (SRS 4.5 business rule)."""

    __tablename__ = "pln_baseline_activity_snapshots"

    baseline_id = db.Column(UUID(as_uuid=True), db.ForeignKey("pln_baselines.id"), nullable=False, index=True)
    activity_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)  # pln_activities.id, not FK-enforced
    # (the source activity may later be deleted; the snapshot must survive that -- see downgrade note in migration)

    planned_start = db.Column(db.Date, nullable=False)
    planned_finish = db.Column(db.Date, nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)

    baseline = relationship("Baseline", back_populates="snapshots")


class LookAheadPlan(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PLN-07: rolling look-ahead plan (e.g. 2-week, 6-week), derived
    from the master schedule but editable at site level without
    altering it -- see LookAheadItem for how that separation is kept."""

    __tablename__ = "pln_look_ahead_plans"

    project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)
    plan_type = db.Column(db.String(16), nullable=False)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)

    items = relationship("LookAheadItem", back_populates="plan", cascade="all, delete-orphan")

    __table_args__ = (db.CheckConstraint(f"plan_type IN {LOOK_AHEAD_TYPES}", name="ck_pln_look_ahead_type"),)


class LookAheadItem(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """A site-level view of one activity within a look-ahead window.
    `adjusted_start`/`adjusted_end` are the site team's working dates --
    editing them does NOT write back to Activity.planned_start (SRS 4.5
    business rule: look-ahead edits happen without altering the master
    schedule)."""

    __tablename__ = "pln_look_ahead_items"

    plan_id = db.Column(UUID(as_uuid=True), db.ForeignKey("pln_look_ahead_plans.id"), nullable=False, index=True)
    activity_id = db.Column(UUID(as_uuid=True), db.ForeignKey("pln_activities.id"), nullable=False, index=True)

    adjusted_start = db.Column(db.Date, nullable=True)
    adjusted_end = db.Column(db.Date, nullable=True)
    site_notes = db.Column(db.Text, nullable=True)
    constraint_flag = db.Column(db.String(64), nullable=True)  # e.g. "awaiting materials", "access blocked"

    plan = relationship("LookAheadPlan", back_populates="items")


class DelayEvent(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """PLN-08: a delay event with cause classification and calculated
    schedule impact. `flagged_for_review` is automatically set when the
    affected activity is on the critical path (SRS 4.5 business rule --
    feeds the Executive Dashboard, Module 21, once it exists)."""

    __tablename__ = "pln_delay_events"

    project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)
    activity_id = db.Column(UUID(as_uuid=True), db.ForeignKey("pln_activities.id"), nullable=True)

    cause_classification = db.Column(db.String(16), nullable=False)
    description = db.Column(db.Text, nullable=False)
    delay_days = db.Column(db.Integer, nullable=False)
    analysis_method = db.Column(db.String(64), nullable=True)  # e.g. "time_impact_analysis"
    occurred_on = db.Column(db.Date, nullable=False)

    affected_critical_path = db.Column(db.Boolean, nullable=False, default=False)
    flagged_for_review = db.Column(db.Boolean, nullable=False, default=False)

    __table_args__ = (db.CheckConstraint(f"cause_classification IN {DELAY_CAUSES}", name="ck_pln_delay_events_cause"),)
