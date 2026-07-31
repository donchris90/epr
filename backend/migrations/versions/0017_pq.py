"""pq module tables

Revision ID: 0017_pq
Revises: 0016_svy
Create Date: 2026-07-30

Creates the tables defined in app/modules/pq/models.py (SRS Section
4.16) and enables Row-Level Security + FORCE + the tenant_isolation
policy on every one of them, per SRS Section 5.5.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0017_pq"
down_revision = "0016_svy"
branch_labels = None
depends_on = None


PQ_TABLES = [
    "pq_crusher_production_records",
    "pq_asphalt_plant_batches",
    "pq_concrete_plant_batches",
    "pq_quarry_production_records",
    "pq_stockpiles",
    "pq_explosives_register",
    "pq_explosives_register_corrections",
    "pq_drilling_records",
    "pq_blasting_records",
    "pq_haulage_records",
    "pq_production_reports",
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
    op.create_table(
        "pq_crusher_production_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("plant_name", sa.String(128), nullable=False),
        sa.Column("shift_date", sa.Date, nullable=False),
        sa.Column("shift", sa.String(16), nullable=True),
        sa.Column("input_material", sa.String(128), nullable=True),
        sa.Column("input_quantity", sa.Numeric(14, 4), nullable=True),
        sa.Column("output_gradation", postgresql.JSONB, nullable=True),
        sa.Column("downtime_minutes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("downtime_reason", sa.Text, nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "pq_asphalt_plant_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("plant_name", sa.String(128), nullable=False),
        sa.Column("mix_design_reference", sa.String(128), nullable=True),
        sa.Column("batch_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("temperature", sa.Numeric(6, 2), nullable=True),
        sa.Column("quantity_produced", sa.Numeric(14, 4), nullable=True),
        sa.Column("unit", sa.String(16), nullable=True),
        sa.Column("lab_result_id", postgresql.UUID(as_uuid=True), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "pq_concrete_plant_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("plant_name", sa.String(128), nullable=False),
        sa.Column("mix_design_reference", sa.String(128), nullable=True),
        sa.Column("batch_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("batch_weights", postgresql.JSONB, nullable=True),
        sa.Column("water_cement_ratio", sa.Numeric(5, 3), nullable=True),
        sa.Column("quantity_produced", sa.Numeric(14, 4), nullable=True),
        sa.Column("destination_pour_reference", postgresql.UUID(as_uuid=True), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "pq_quarry_production_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("quarry_name", sa.String(128), nullable=False),
        sa.Column("face_or_bench", sa.String(128), nullable=True),
        sa.Column("material_type", sa.String(128), nullable=True),
        sa.Column("volume_extracted", sa.Numeric(14, 4), nullable=True),
        sa.Column("production_date", sa.Date, nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "pq_stockpiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("material_type", sa.String(128), nullable=False),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("last_reconciled_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "pq_explosives_register",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("entry_type", sa.String(16), nullable=False),
        sa.Column("material_type", sa.String(128), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("entry_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reference_number", sa.String(128), nullable=True),
        sa.Column("recorded_by", postgresql.UUID(as_uuid=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(
            "entry_type IN ('procurement','storage','issuance','consumption')", name="ck_pq_explosives_entry_type"
        ),
    )

    op.create_table(
        "pq_explosives_register_corrections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pq_explosives_register.id"), nullable=False, index=True),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("corrected_quantity", sa.Numeric(14, 4), nullable=True),
        sa.Column("corrected_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("corrected_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "pq_drilling_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("quarry_name", sa.String(128), nullable=False),
        sa.Column("pattern_reference", sa.String(128), nullable=True),
        sa.Column("hole_count", sa.Integer, nullable=True),
        sa.Column("depth", sa.Numeric(8, 2), nullable=True),
        sa.Column("drilled_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "pq_blasting_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("drilling_record_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pq_drilling_records.id"), nullable=False, index=True),
        sa.Column("explosives_used", postgresql.JSONB, nullable=True),
        sa.Column("blast_design", sa.Text, nullable=True),
        sa.Column("vibration_monitoring_result", sa.Numeric(10, 4), nullable=True),
        sa.Column("fly_rock_monitoring_result", sa.Text, nullable=True),
        sa.Column("regulatory_notification_reference", sa.String(128), nullable=True),
        sa.Column("blast_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="planned"),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('planned','completed')", name="ck_pq_blasting_status"),
    )

    op.create_table(
        "pq_haulage_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("source", sa.String(128), nullable=True),
        sa.Column("destination", sa.String(128), nullable=True),
        sa.Column("load_count", sa.Integer, nullable=True),
        sa.Column("tonnage", sa.Numeric(14, 4), nullable=True),
        sa.Column("cycle_time_minutes", sa.Integer, nullable=True),
        sa.Column("haul_date", sa.Date, nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "pq_production_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("plant_or_quarry_name", sa.String(128), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("total_output", sa.Numeric(14, 4), nullable=True),
        sa.Column("yield_efficiency_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("cost_per_unit", sa.Numeric(14, 4), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
    )

    for table in PQ_TABLES:
        _enable_rls(table)


def downgrade():
    for table in reversed(PQ_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("pq_production_reports")
    op.drop_table("pq_haulage_records")
    op.drop_table("pq_blasting_records")
    op.drop_table("pq_drilling_records")
    op.drop_table("pq_explosives_register_corrections")
    op.drop_table("pq_explosives_register")
    op.drop_table("pq_stockpiles")
    op.drop_table("pq_quarry_production_records")
    op.drop_table("pq_concrete_plant_batches")
    op.drop_table("pq_asphalt_plant_batches")
    op.drop_table("pq_crusher_production_records")
