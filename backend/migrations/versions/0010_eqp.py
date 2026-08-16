"""eqp module tables

Revision ID: 0010_eqp
Revises: 0009_inv
Create Date: 2026-07-27

Creates the tables defined in app/modules/eqp/models.py (SRS Section 4.9)
and enables Row-Level Security + FORCE + the tenant_isolation policy on
every one of them, per SRS Section 5.5.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_eqp"
down_revision = "0009_inv"
branch_labels = None
depends_on = None


EQP_TABLES = [
    "eqp_equipment",
    "eqp_gps_positions",
    "eqp_operator_assignments",
    "eqp_maintenance_records",
    "eqp_spare_part_usages",
    "eqp_repair_history",
    "eqp_downtime_events",
    "eqp_utilization_records",
    "eqp_equipment_transfers",
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
        "eqp_equipment",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("make", sa.String(128), nullable=True),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("serial_chassis_number", sa.String(128), nullable=True),
        sa.Column("ownership_type", sa.String(16), nullable=False, server_default="owned"),
        sa.Column("acquisition_cost", sa.Numeric(18, 4), nullable=True),
        sa.Column("acquisition_date", sa.Date, nullable=True),
        sa.Column("salvage_value", sa.Numeric(18, 4), nullable=True, server_default="0"),
        sa.Column("useful_life_years", sa.Integer, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active", index=True),
        sa.Column("current_project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        *_audit_columns(),
        sa.CheckConstraint("ownership_type IN ('owned','rented')", name="ck_eqp_equipment_ownership"),
        sa.CheckConstraint("status IN ('active','under_maintenance','idle','disposed')", name="ck_eqp_equipment_status"),
    )

    op.create_table(
        "eqp_gps_positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("equipment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("eqp_equipment.id"), nullable=False, index=True),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("source", sa.String(16), nullable=False, server_default="gps_device"),
        *_audit_columns(),
        sa.CheckConstraint("source IN ('gps_device','manual')", name="ck_eqp_gps_positions_source"),
    )

    op.create_table(
        "eqp_operator_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("equipment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("eqp_equipment.id"), nullable=False, index=True),
        sa.Column("operator_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("shift_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("shift_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("certification_valid_until", sa.Date, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('active','completed','cancelled')", name="ck_eqp_operator_assignments_status"),
    )

    op.create_table(
        "eqp_maintenance_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("equipment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("eqp_equipment.id"), nullable=False, index=True),
        sa.Column("maintenance_type", sa.String(16), nullable=False, server_default="scheduled"),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("due_at_hours", sa.Numeric(10, 1), nullable=True),
        sa.Column("due_at_date", sa.Date, nullable=True, index=True),
        sa.Column("due_at_mileage", sa.Numeric(10, 1), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cost", sa.Numeric(18, 4), nullable=True),
        sa.Column("performed_by", sa.String(255), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="scheduled"),
        *_audit_columns(),
        sa.CheckConstraint("maintenance_type IN ('scheduled','unscheduled')", name="ck_eqp_maintenance_type"),
        sa.CheckConstraint("status IN ('scheduled','completed','overdue')", name="ck_eqp_maintenance_status"),
    )

    op.create_table(
        "eqp_spare_part_usages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("maintenance_record_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("eqp_maintenance_records.id"), nullable=False, index=True),
        sa.Column("material_item_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "eqp_repair_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("equipment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("eqp_equipment.id"), nullable=False, index=True),
        sa.Column("maintenance_record_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("eqp_maintenance_records.id"), nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("cost", sa.Numeric(18, 4), nullable=True),
        sa.Column("downtime_hours", sa.Numeric(8, 2), nullable=True),
        sa.Column("root_cause", sa.Text, nullable=True),
        sa.Column("repaired_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "eqp_downtime_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("equipment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("eqp_equipment.id"), nullable=False, index=True),
        sa.Column("reason_classification", sa.String(24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(
            "reason_classification IN ('breakdown','scheduled_maintenance','awaiting_parts','idle_no_work')",
            name="ck_eqp_downtime_reason",
        ),
    )

    op.create_table(
        "eqp_utilization_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("equipment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("eqp_equipment.id"), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("record_date", sa.Date, nullable=False, index=True),
        sa.Column("hours_operated", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("hours_scheduled", sa.Numeric(6, 2), nullable=False, server_default="0"),
        *_audit_columns(),
    )

    op.create_table(
        "eqp_equipment_transfers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("equipment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("eqp_equipment.id"), nullable=False, index=True),
        sa.Column("from_project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("to_project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cutover_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('pending','approved','rejected')", name="ck_eqp_transfers_status"),
    )

    for table in EQP_TABLES:
        _enable_rls(table)


def downgrade():
    for table in reversed(EQP_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("eqp_equipment_transfers")
    op.drop_table("eqp_utilization_records")
    op.drop_table("eqp_downtime_events")
    op.drop_table("eqp_repair_history")
    op.drop_table("eqp_spare_part_usages")
    op.drop_table("eqp_maintenance_records")
    op.drop_table("eqp_operator_assignments")
    op.drop_table("eqp_gps_positions")
    op.drop_table("eqp_equipment")
