"""factory manufacturing: BOMs, work centers, production orders

Revision ID: 0063_factory_manufacturing
Revises: 0062_dsar_public_intake
Create Date: 2026-10-26

Adds item types and a quality-hold status on batches to inventory, and the
manufacturing tables (work centers, BOMs, production orders and their
component snapshots). Every new table is RLS-isolated like the rest.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0063_factory_manufacturing"
down_revision = "0062_dsar_public_intake"
branch_labels = None
depends_on = None

ITEM_TYPES = "('raw_material', 'semi_finished', 'finished_good', 'consumable', 'other')"
BATCH_STATUSES = "('released', 'quarantined', 'rejected')"
ORDER_STATUSES = "('draft', 'released', 'in_progress', 'done', 'cancelled')"
NEW_TABLES = ["mfg_work_centers", "mfg_boms", "mfg_bom_lines", "mfg_production_orders", "mfg_production_components"]


def _uuid_pk():
    return sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"))


def _tenant():
    return sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True)


def _audit():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    ]


def _uuid(name, fk=None, nullable=False, index=False, ondelete=None):
    args = [sa.ForeignKey(fk, ondelete=ondelete)] if fk else []
    return sa.Column(name, postgresql.UUID(as_uuid=True), *args, nullable=nullable, index=index)


def upgrade():
    op.add_column("inv_material_items", sa.Column("item_type", sa.String(24), nullable=False, server_default="other"))
    op.create_check_constraint("ck_inv_material_items_item_type", "inv_material_items", f"item_type IN {ITEM_TYPES}")
    op.add_column("inv_batch_numbers", sa.Column("status", sa.String(16), nullable=False, server_default="released"))
    op.add_column("inv_batch_numbers", sa.Column("production_order_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_inv_batch_numbers_production_order_id", "inv_batch_numbers", ["production_order_id"])
    op.create_check_constraint("ck_inv_batch_numbers_status", "inv_batch_numbers", f"status IN {BATCH_STATUSES}")

    op.create_table(
        "mfg_work_centers",
        _uuid_pk(), _tenant(),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("hourly_rate", sa.Numeric(18, 4), nullable=False, server_default="0"),
        _uuid("equipment_id", nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        *_audit(),
        sa.UniqueConstraint("tenant_id", "code", name="uq_mfg_work_centers_tenant_code"),
        sa.CheckConstraint("hourly_rate >= 0", name="ck_mfg_work_centers_rate"),
    )
    op.create_table(
        "mfg_boms",
        _uuid_pk(), _tenant(),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        _uuid("product_item_id", "inv_material_items.id", index=True),
        sa.Column("output_quantity", sa.Numeric(18, 4), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        *_audit(),
        sa.UniqueConstraint("tenant_id", "code", name="uq_mfg_boms_tenant_code"),
        sa.CheckConstraint("output_quantity > 0", name="ck_mfg_boms_output_positive"),
    )
    op.create_table(
        "mfg_bom_lines",
        _uuid_pk(), _tenant(),
        _uuid("bom_id", "mfg_boms.id", index=True, ondelete="CASCADE"),
        _uuid("component_item_id", "inv_material_items.id"),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("scrap_percent", sa.Numeric(7, 3), nullable=False, server_default="0"),
        *_audit(),
        sa.UniqueConstraint("bom_id", "component_item_id", name="uq_mfg_bom_lines_bom_component"),
        sa.CheckConstraint("quantity > 0", name="ck_mfg_bom_lines_qty_positive"),
        sa.CheckConstraint("scrap_percent >= 0 AND scrap_percent < 100", name="ck_mfg_bom_lines_scrap_range"),
    )
    op.create_table(
        "mfg_production_orders",
        _uuid_pk(), _tenant(),
        sa.Column("number", sa.String(32), nullable=False),
        _uuid("bom_id", "mfg_boms.id", index=True),
        _uuid("product_item_id", "inv_material_items.id"),
        _uuid("warehouse_id", "inv_warehouses.id"),
        _uuid("work_center_id", "mfg_work_centers.id", nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("quantity_planned", sa.Numeric(18, 4), nullable=False),
        sa.Column("quantity_produced", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("quantity_scrapped", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("planned_start", sa.Date, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("labour_hours", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("fuel_litres", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("material_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("labour_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("fuel_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
        _uuid("batch_id", nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        *_audit(),
        sa.UniqueConstraint("tenant_id", "number", name="uq_mfg_production_orders_tenant_number"),
        sa.CheckConstraint(f"status IN {ORDER_STATUSES}", name="ck_mfg_production_orders_status"),
        sa.CheckConstraint("quantity_planned > 0", name="ck_mfg_production_orders_planned_positive"),
    )
    op.create_table(
        "mfg_production_components",
        _uuid_pk(), _tenant(),
        _uuid("order_id", "mfg_production_orders.id", index=True, ondelete="CASCADE"),
        _uuid("component_item_id", "inv_material_items.id"),
        sa.Column("planned_quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("consumed_quantity", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("valued_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
        *_audit(),
    )

    for table in NEW_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON {table} USING (tenant_id = current_setting('app.tenant_id')::uuid)")


def downgrade():
    for table in reversed(NEW_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.drop_table(table)
    op.drop_constraint("ck_inv_batch_numbers_status", "inv_batch_numbers", type_="check")
    op.drop_index("ix_inv_batch_numbers_production_order_id", table_name="inv_batch_numbers")
    op.drop_column("inv_batch_numbers", "production_order_id")
    op.drop_column("inv_batch_numbers", "status")
    op.drop_constraint("ck_inv_material_items_item_type", "inv_material_items", type_="check")
    op.drop_column("inv_material_items", "item_type")
