"""hse module tables

Revision ID: 0015_hse
Revises: 0014_qms
Create Date: 2026-07-30

Creates the tables defined in app/modules/hse/models.py (SRS Section
4.14) and enables Row-Level Security + FORCE + the tenant_isolation
policy on every one of them, per SRS Section 5.5.

Also alters Module 13's qms_corrective_actions.source check constraint
to add 'incident' -- Module 14's business rule requires every
recordable incident to generate a linked Corrective Action, and that
needs a source value distinct from 'ncr'/'audit' to be honest about
where it came from.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0015_hse"
down_revision = "0014_qms"
branch_labels = None
depends_on = None


HSE_TABLES = [
    "hse_risk_assessments",
    "hse_permits_to_work",
    "hse_incidents",
    "hse_near_misses",
    "hse_toolbox_talks",
    "hse_toolbox_talk_attendees",
    "hse_ppe_records",
    "hse_safety_audits",
    "hse_environmental_monitoring_records",
    "hse_waste_disposal_records",
    "hse_emergency_response_plans",
]


def _audit_columns():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    ]


def _enable_rls(table_name: str):
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {table_name}
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def upgrade():
    # --- Extend QMS's corrective action source constraint ---
    op.execute("ALTER TABLE qms_corrective_actions DROP CONSTRAINT ck_qms_corrective_actions_source")
    op.execute(
        "ALTER TABLE qms_corrective_actions ADD CONSTRAINT ck_qms_corrective_actions_source "
        "CHECK (source IN ('ncr','audit','incident'))"
    )

    op.create_table(
        "hse_risk_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("activity_or_area", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("risk_level", sa.String(16), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.Date, nullable=True, index=True),
        sa.Column("review_interval_days", sa.Integer, nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('active','expired','superseded')", name="ck_hse_risk_status"),
    )

    op.create_table(
        "hse_permits_to_work",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("risk_assessment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hse_risk_assessments.id"), nullable=True),
        sa.Column("permit_type", sa.String(24), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft", index=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("formally_closed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by", postgresql.UUID(as_uuid=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(
            "permit_type IN ('hot_work','confined_space','excavation','working_at_height')", name="ck_hse_permits_type"
        ),
        sa.CheckConstraint("status IN ('draft','approved','active','closed')", name="ck_hse_permits_status"),
    )

    op.create_table(
        "hse_incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("classification", sa.String(24), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("investigation_findings", sa.Text, nullable=True),
        sa.Column("regulatory_reportable", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reported_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("corrective_action_id", postgresql.UUID(as_uuid=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(
            "classification IN ('first_aid','medical_treatment','lost_time','fatality')",
            name="ck_hse_incidents_classification",
        ),
        sa.CheckConstraint("status IN ('open','closed')", name="ck_hse_incidents_status"),
    )

    op.create_table(
        "hse_near_misses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("classification", sa.String(24), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reported_by", postgresql.UUID(as_uuid=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(
            "classification IN ('first_aid','medical_treatment','lost_time','fatality')",
            name="ck_hse_near_misses_classification",
        ),
    )

    op.create_table(
        "hse_toolbox_talks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("topic", sa.String(255), nullable=False),
        sa.Column("facilitator_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("held_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("facilitator_signed", sa.Boolean, nullable=False, server_default=sa.false()),
        *_audit_columns(),
    )

    op.create_table(
        "hse_toolbox_talk_attendees",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("talk_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hse_toolbox_talks.id"), nullable=False, index=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("casual_worker_id", postgresql.UUID(as_uuid=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(
            "(employee_id IS NOT NULL AND casual_worker_id IS NULL) OR "
            "(employee_id IS NULL AND casual_worker_id IS NOT NULL)",
            name="ck_hse_talk_attendees_exactly_one_worker",
        ),
    )

    op.create_table(
        "hse_ppe_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("casual_worker_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("material_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ppe_type", sa.String(128), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(
            "(employee_id IS NOT NULL AND casual_worker_id IS NULL) OR "
            "(employee_id IS NULL AND casual_worker_id IS NOT NULL)",
            name="ck_hse_ppe_records_exactly_one_worker",
        ),
    )

    op.create_table(
        "hse_safety_audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("audit_type", sa.String(16), nullable=False, server_default="scheduled"),
        sa.Column("checklist", postgresql.JSONB, nullable=True),
        sa.Column("score", sa.Numeric(5, 2), nullable=True),
        sa.Column("audit_date", sa.Date, nullable=True),
        sa.Column("auditor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("corrective_action_id", postgresql.UUID(as_uuid=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("audit_type IN ('scheduled','ad_hoc')", name="ck_hse_audits_type"),
    )

    op.create_table(
        "hse_environmental_monitoring_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("monitoring_type", sa.String(16), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("value", sa.Numeric(12, 4), nullable=True),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("threshold", sa.Numeric(12, 4), nullable=True),
        sa.Column("exceeds_threshold", sa.Boolean, nullable=False, server_default=sa.false()),
        *_audit_columns(),
        sa.CheckConstraint("monitoring_type IN ('dust','noise','water_discharge')", name="ck_hse_env_monitoring_type"),
    )

    op.create_table(
        "hse_waste_disposal_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("waste_type", sa.String(16), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 4), nullable=True),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("disposed_at", sa.Date, nullable=True),
        sa.Column("manifest_document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("disposal_certificate_document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("waste_type IN ('construction','hazardous')", name="ck_hse_waste_type"),
    )

    op.create_table(
        "hse_emergency_response_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("muster_points", postgresql.JSONB, nullable=True),
        sa.Column("emergency_contacts", postgresql.JSONB, nullable=True),
        sa.Column("designated_roles", postgresql.JSONB, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("effective_from", sa.Date, nullable=True),
        *_audit_columns(),
    )

    for table in HSE_TABLES:
        _enable_rls(table)


def downgrade():
    for table in reversed(HSE_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("hse_emergency_response_plans")
    op.drop_table("hse_waste_disposal_records")
    op.drop_table("hse_environmental_monitoring_records")
    op.drop_table("hse_safety_audits")
    op.drop_table("hse_ppe_records")
    op.drop_table("hse_toolbox_talk_attendees")
    op.drop_table("hse_toolbox_talks")
    op.drop_table("hse_near_misses")
    op.drop_table("hse_incidents")
    op.drop_table("hse_permits_to_work")
    op.drop_table("hse_risk_assessments")

    op.execute("ALTER TABLE qms_corrective_actions DROP CONSTRAINT ck_qms_corrective_actions_source")
    op.execute(
        "ALTER TABLE qms_corrective_actions ADD CONSTRAINT ck_qms_corrective_actions_source "
        "CHECK (source IN ('ncr','audit'))"
    )
