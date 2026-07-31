"""
Module 20 — Asset Management (Code: AST)
SRS Section 4.20.

Manages the completed infrastructure after project handover -- relevant
both for contractors retained on maintenance contracts and for
public-sector/asset-owner clients using SiteForge post-construction.

Key Data Entities (SRS 4.20): Asset (Building/Road/Bridge/Drainage/
Utility), MaintenanceSchedule, AssetInspection, WarrantyRecord,
DefectsLiabilityRecord, LifecycleCostRecord.

Design notes:
  - `DefectItem` is not in the SRS's named entity list but is what the
    DLP business rule actually needs to check against -- a
    DefectsLiabilityRecord needs individual, independently trackable
    defects with their own resolved/verified states (the same
    resolved-vs-verified distinction already established for Module
    13's CorrectiveAction, reused here for the same reason: completing
    a fix and someone independently confirming it worked are different
    facts).
  - There is no separate "condition event" table distinct from
    AssetInspection -- SRS 4.20's business rule that "subsequent
    changes are recorded as dated condition/maintenance events layered
    on top of that baseline" is satisfied by AssetInspection rows
    themselves (each one IS a dated condition event) plus
    LifecycleCostRecord for maintenance spend events; adding a third,
    more generic "event" table would just duplicate what those two
    already are.
  - Business rule (SRS 4.20): an Asset's original as-built baseline
    (`baseline_data`, `as_built_record_id`, `handover_date`) is
    immutable once created -- there is no route or service function
    anywhere in this module that can change those three fields after
    creation. `name` and `category_attributes` (general descriptive
    data, not as-built baseline data) ARE editable via
    services.update_asset_attributes, a narrow function that touches
    only those fields, never the baseline ones.
  - Business rule (SRS 4.20): DLP retention release requires every
    DefectItem raised during the DLP to be VERIFIED (not merely
    resolved) -- enforced in services.release_dlp_retention.
"""
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin


ASSET_CATEGORIES = ("building", "road", "bridge", "drainage", "utility")
MAINTENANCE_TASK_TYPES = ("routine", "periodic")
WARRANTY_STATUSES = ("active", "expired")
DEFECT_STATUSES = ("open", "resolved", "verified")
LIFECYCLE_COST_TYPES = ("maintenance", "rehabilitation")


class Asset(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """AST-01, AST-02, AST-08: created at handover from Module 15's
    As-Built Records, category-specific attributes, hierarchical
    structuring via self-referential parent_asset_id. Business rule:
    baseline_data/as_built_record_id/handover_date are immutable once
    set -- see module docstring."""

    __tablename__ = "ast_assets"

    project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)
    parent_asset_id = db.Column(UUID(as_uuid=True), db.ForeignKey("ast_assets.id"), nullable=True, index=True)
    as_built_record_id = db.Column(UUID(as_uuid=True), nullable=True)  # svy_as_built_records.id, loose reference

    asset_category = db.Column(db.String(16), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    category_attributes = db.Column(JSONB, nullable=True)  # category-specific attribute set (AST-02)
    baseline_data = db.Column(JSONB, nullable=True)  # frozen as-built position/level/scope snapshot at handover
    handover_date = db.Column(db.Date, nullable=True)

    children = relationship("Asset", backref=db.backref("parent", remote_side="Asset.id"))

    __table_args__ = (db.CheckConstraint(f"asset_category IN {ASSET_CATEGORIES}", name="ck_ast_assets_category"),)


class MaintenanceSchedule(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """AST-03: recurring maintenance tasks (routine/periodic) with
    due-date tracking. A rolling schedule -- completing a task advances
    `next_due_date` by `frequency_days` rather than spawning a separate
    task-instance table, keeping the "next thing due" always a single
    live fact per schedule."""

    __tablename__ = "ast_maintenance_schedules"

    asset_id = db.Column(UUID(as_uuid=True), db.ForeignKey("ast_assets.id"), nullable=False, index=True)
    task_name = db.Column(db.String(255), nullable=False)
    task_type = db.Column(db.String(16), nullable=False, default="routine")
    frequency_days = db.Column(db.Integer, nullable=True)  # null for a one-off task
    next_due_date = db.Column(db.Date, nullable=True, index=True)
    last_completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (db.CheckConstraint(f"task_type IN {MAINTENANCE_TASK_TYPES}", name="ck_ast_maint_task_type"),)


class AssetInspection(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """AST-04: condition scoring (e.g. a pavement/structural condition
    index) with photographic evidence -- each row IS a dated condition
    event layered on top of the asset's immutable baseline."""

    __tablename__ = "ast_asset_inspections"

    asset_id = db.Column(UUID(as_uuid=True), db.ForeignKey("ast_assets.id"), nullable=False, index=True)
    inspected_at = db.Column(db.Date, nullable=True)
    condition_score = db.Column(db.Numeric(6, 2), nullable=True)  # scale is tenant/category convention
    inspector_name = db.Column(db.String(255), nullable=True)
    photo_document_ids = db.Column(JSONB, nullable=True)  # list of documents.id, as strings
    notes = db.Column(db.Text, nullable=True)


class WarrantyRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """AST-05: per asset/component, with expiry alerts."""

    __tablename__ = "ast_warranty_records"

    asset_id = db.Column(UUID(as_uuid=True), db.ForeignKey("ast_assets.id"), nullable=False, index=True)
    component_name = db.Column(db.String(255), nullable=True)
    warranty_provider = db.Column(db.String(255), nullable=True)
    valid_until = db.Column(db.Date, nullable=True, index=True)


class DefectsLiabilityRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """AST-06: business rule -- retention release requires every linked
    DefectItem to be VERIFIED, not merely resolved (services.py)."""

    __tablename__ = "ast_defects_liability_records"

    asset_id = db.Column(UUID(as_uuid=True), db.ForeignKey("ast_assets.id"), nullable=False, index=True)
    contract_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)  # ctm_contracts.id, loose reference

    dlp_start = db.Column(db.Date, nullable=True)
    dlp_end = db.Column(db.Date, nullable=True)
    retention_released = db.Column(db.Boolean, nullable=False, default=False)
    released_at = db.Column(db.DateTime(timezone=True), nullable=True)

    defects = relationship("DefectItem", back_populates="dlp_record", cascade="all, delete-orphan")


class DefectItem(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """The individually trackable defect the DLP business rule checks
    against -- resolved and verified are deliberately distinct states,
    the same reasoning as Module 13's CorrectiveAction."""

    __tablename__ = "ast_defect_items"

    dlp_record_id = db.Column(UUID(as_uuid=True), db.ForeignKey("ast_defects_liability_records.id"), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="open")
    raised_at = db.Column(db.Date, nullable=True)
    resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    verified_at = db.Column(db.DateTime(timezone=True), nullable=True)
    verified_by = db.Column(UUID(as_uuid=True), nullable=True)

    dlp_record = relationship("DefectsLiabilityRecord", back_populates="defects")

    __table_args__ = (db.CheckConstraint(f"status IN {DEFECT_STATUSES}", name="ck_ast_defect_status"),)


class LifecycleCostRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """AST-07: maintenance and rehabilitation spend against an asset
    over its operational life, for whole-life-cost reporting."""

    __tablename__ = "ast_lifecycle_cost_records"

    asset_id = db.Column(UUID(as_uuid=True), db.ForeignKey("ast_assets.id"), nullable=False, index=True)
    cost_type = db.Column(db.String(16), nullable=False)
    amount = db.Column(db.Numeric(18, 4), nullable=False)
    incurred_at = db.Column(db.Date, nullable=True)
    description = db.Column(db.Text, nullable=True)

    __table_args__ = (db.CheckConstraint(f"cost_type IN {LIFECYCLE_COST_TYPES}", name="ck_ast_lifecycle_cost_type"),)
