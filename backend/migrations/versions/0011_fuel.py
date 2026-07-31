"""fuel module tables

Revision ID: 0011_fuel
Revises: 0010_eqp
Create Date: 2026-07-28

Creates the tables defined in app/modules/fuel/models.py (SRS Section
4.10) and enables Row-Level Security + FORCE + the tenant_isolation
policy on every one of them, per SRS Section 5.5.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0011_fuel"
down_revision = "0010_eqp"
branch_labels = None
depends_on = None


FUEL_TABLES = [
    "fuel_tanks",
    "fuel_purchases",
    "fuel_issues",
    "fuel_burn_rate_profiles",
    "fuel_variance_records",
    "fuel_theft_flags",
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
        "fuel_tanks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("tank_type", sa.String(24), nullable=False),
        sa.Column("capacity_litres", sa.Numeric(10, 2), nullable=True),
        sa.Column("current_level_litres", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("equipment_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        *_audit_columns(),
        sa.CheckConstraint("tank_type IN ('bulk_storage','equipment_onboard')", name="ck_fuel_tanks_type"),
    )

    op.create_table(
        "fuel_purchases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("tank_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fuel_tanks.id"), nullable=False, index=True),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("quantity_litres", sa.Numeric(10, 2), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 4), nullable=False),
        sa.Column("total_cost", sa.Numeric(18, 4), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_confirmed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("confirmed_by", postgresql.UUID(as_uuid=True), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "fuel_issues",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("tank_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fuel_tanks.id"), nullable=False, index=True),
        sa.Column("equipment_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("operator_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("quantity_litres", sa.Numeric(10, 2), nullable=False),
        sa.Column("meter_reading", sa.Numeric(12, 2), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("issued_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("requires_countersignature", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("countersigned", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("countersigned_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("countersigned_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "fuel_burn_rate_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("equipment_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True, index=True),
        sa.Column("expected_litres_per_hour", sa.Numeric(8, 2), nullable=False),
        sa.Column("source", sa.String(24), nullable=False, server_default="historical"),
        *_audit_columns(),
    )

    op.create_table(
        "fuel_variance_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("equipment_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("expected_litres", sa.Numeric(10, 2), nullable=False),
        sa.Column("actual_litres", sa.Numeric(10, 2), nullable=False),
        sa.Column("variance_litres", sa.Numeric(10, 2), nullable=False),
        sa.Column("variance_pct", sa.Numeric(6, 2), nullable=True),
        sa.Column("unit_price_used", sa.Numeric(10, 4), nullable=True),
        sa.Column("variance_cost", sa.Numeric(18, 4), nullable=True),
        *_audit_columns(),
        sa.UniqueConstraint("equipment_id", "period_start", "period_end", name="uq_fuel_variance_equipment_period"),
    )

    op.create_table(
        "fuel_theft_flags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("equipment_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("tank_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fuel_tanks.id"), nullable=True),
        sa.Column("fuel_issue_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fuel_issues.id"), nullable=True),
        sa.Column("flag_reason", sa.String(32), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="open", index=True),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("raised_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(
            "flag_reason IN ('variance_threshold_exceeded','no_usage_log','tank_level_mismatch')",
            name="ck_fuel_theft_flags_reason",
        ),
        sa.CheckConstraint("status IN ('open','reviewing','resolved','escalated')", name="ck_fuel_theft_flags_status"),
    )

    for table in FUEL_TABLES:
        _enable_rls(table)


def downgrade():
    for table in reversed(FUEL_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("fuel_theft_flags")
    op.drop_table("fuel_variance_records")
    op.drop_table("fuel_burn_rate_profiles")
    op.drop_table("fuel_issues")
    op.drop_table("fuel_purchases")
    op.drop_table("fuel_tanks")
