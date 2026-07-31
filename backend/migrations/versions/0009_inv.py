"""inv module tables

Revision ID: 0009_inv
Revises: 0008_prc
Create Date: 2026-07-27

Creates the tables defined in app/modules/inv/models.py (SRS Section 4.8)
and enables Row-Level Security + FORCE + the tenant_isolation policy on
every one of them, per SRS Section 5.5.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009_inv"
down_revision = "0008_prc"
branch_labels = None
depends_on = None


INV_TABLES = [
    "inv_settings",
    "inv_warehouses",
    "inv_material_items",
    "inv_stock_items",
    "inv_stock_layers",
    "inv_stock_transfers",
    "inv_stock_reservations",
    "inv_reorder_levels",
    "inv_item_codes",
    "inv_batch_numbers",
    "inv_serial_numbers",
    "inv_waste_records",
    "inv_material_returns",
    "inv_stock_counts",
    "inv_stock_count_lines",
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
        "inv_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("valuation_method", sa.String(16), nullable=False, server_default="weighted_average"),
        *_audit_columns(),
        sa.CheckConstraint("valuation_method IN ('weighted_average','fifo')", name="ck_inv_settings_valuation_method"),
        sa.UniqueConstraint("tenant_id", name="uq_inv_settings_tenant"),
    )

    op.create_table(
        "inv_warehouses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("warehouse_type", sa.String(16), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("location", sa.String(255), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("warehouse_type IN ('central_yard','site_store','quarry')", name="ck_inv_warehouses_type"),
    )

    op.create_table(
        "inv_material_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("is_batch_tracked", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_serial_tracked", sa.Boolean, nullable=False, server_default=sa.false()),
        *_audit_columns(),
        sa.UniqueConstraint("tenant_id", "code", name="uq_inv_material_items_tenant_code"),
    )

    op.create_table(
        "inv_stock_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inv_warehouses.id"), nullable=False, index=True),
        sa.Column("material_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inv_material_items.id"), nullable=False, index=True),
        sa.Column("quantity_on_hand", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("average_unit_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
        *_audit_columns(),
        sa.CheckConstraint("quantity_on_hand >= 0", name="ck_inv_stock_items_qty_non_negative"),
        sa.UniqueConstraint("warehouse_id", "material_item_id", name="uq_inv_stock_items_warehouse_material"),
    )

    op.create_table(
        "inv_stock_layers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inv_warehouses.id"), nullable=False, index=True),
        sa.Column("material_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inv_material_items.id"), nullable=False, index=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quantity_remaining", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False),
        *_audit_columns(),
        sa.CheckConstraint("quantity_remaining >= 0", name="ck_inv_stock_layers_qty_non_negative"),
    )

    op.create_table(
        "inv_stock_transfers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("from_warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inv_warehouses.id"), nullable=False, index=True),
        sa.Column("to_warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inv_warehouses.id"), nullable=False, index=True),
        sa.Column("material_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inv_material_items.id"), nullable=False, index=True),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="in_transit"),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispatched_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_by", postgresql.UUID(as_uuid=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('in_transit','received')", name="ck_inv_stock_transfers_status"),
        sa.CheckConstraint("from_warehouse_id != to_warehouse_id", name="ck_inv_stock_transfers_diff_warehouses"),
    )

    op.create_table(
        "inv_stock_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inv_warehouses.id"), nullable=False, index=True),
        sa.Column("material_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inv_material_items.id"), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("reserved_by", postgresql.UUID(as_uuid=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('active','released','consumed')", name="ck_inv_stock_reservations_status"),
    )

    op.create_table(
        "inv_reorder_levels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inv_warehouses.id"), nullable=False, index=True),
        sa.Column("material_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inv_material_items.id"), nullable=False, index=True),
        sa.Column("reorder_point", sa.Numeric(18, 4), nullable=False),
        sa.Column("reorder_quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("auto_create_pr", sa.Boolean, nullable=False, server_default=sa.false()),
        *_audit_columns(),
        sa.UniqueConstraint("warehouse_id", "material_item_id", name="uq_inv_reorder_levels_warehouse_material"),
    )

    op.create_table(
        "inv_item_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("material_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inv_material_items.id"), nullable=False, index=True),
        sa.Column("code_type", sa.String(8), nullable=False),
        sa.Column("code_value", sa.String(128), nullable=False),
        *_audit_columns(),
        sa.CheckConstraint("code_type IN ('barcode','qr')", name="ck_inv_item_codes_type"),
        sa.UniqueConstraint("tenant_id", "code_value", name="uq_inv_item_codes_tenant_value"),
    )

    op.create_table(
        "inv_batch_numbers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("material_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inv_material_items.id"), nullable=False, index=True),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inv_warehouses.id"), nullable=False, index=True),
        sa.Column("batch_number", sa.String(128), nullable=False),
        sa.Column("manufactured_date", sa.Date, nullable=True),
        sa.Column("expiry_date", sa.Date, nullable=True, index=True),
        sa.Column("quality_cert_document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("quantity_remaining", sa.Numeric(18, 4), nullable=False, server_default="0"),
        *_audit_columns(),
    )

    op.create_table(
        "inv_serial_numbers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("material_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inv_material_items.id"), nullable=False, index=True),
        sa.Column("serial_number", sa.String(128), nullable=False),
        sa.Column("current_warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inv_warehouses.id"), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="in_stock"),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('in_stock','issued','disposed')", name="ck_inv_serial_numbers_status"),
        sa.UniqueConstraint("tenant_id", "serial_number", name="uq_inv_serial_numbers_tenant_serial"),
    )

    op.create_table(
        "inv_waste_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inv_warehouses.id"), nullable=False, index=True),
        sa.Column("material_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inv_material_items.id"), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("cause_classification", sa.String(16), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("valued_cost", sa.Numeric(18, 4), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("cause_classification IN ('breakage','theft','spoilage','over_order')", name="ck_inv_waste_records_cause"),
    )

    op.create_table(
        "inv_material_returns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("material_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inv_material_items.id"), nullable=False, index=True),
        sa.Column("source_warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inv_warehouses.id"), nullable=False),
        sa.Column("destination_warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inv_warehouses.id"), nullable=True),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("return_type", sa.String(16), nullable=False),
        sa.Column("condition", sa.String(16), nullable=False, server_default="good"),
        sa.Column("credit_note_reference", sa.String(128), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        *_audit_columns(),
        sa.CheckConstraint("return_type IN ('site_to_yard','to_vendor')", name="ck_inv_material_returns_type"),
        sa.CheckConstraint("condition IN ('good','damaged')", name="ck_inv_material_returns_condition"),
        sa.CheckConstraint("status IN ('pending','completed')", name="ck_inv_material_returns_status"),
    )

    op.create_table(
        "inv_stock_counts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inv_warehouses.id"), nullable=False, index=True),
        sa.Column("count_type", sa.String(8), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("counted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("counted_by", postgresql.UUID(as_uuid=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("count_type IN ('cycle','full')", name="ck_inv_stock_counts_type"),
        sa.CheckConstraint("status IN ('draft','completed','adjusted')", name="ck_inv_stock_counts_status"),
    )

    op.create_table(
        "inv_stock_count_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("stock_count_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inv_stock_counts.id"), nullable=False, index=True),
        sa.Column("material_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inv_material_items.id"), nullable=False, index=True),
        sa.Column("system_quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("counted_quantity", sa.Numeric(18, 4), nullable=True),
        *_audit_columns(),
    )

    for table in INV_TABLES:
        _enable_rls(table)


def downgrade():
    for table in reversed(INV_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("inv_stock_count_lines")
    op.drop_table("inv_stock_counts")
    op.drop_table("inv_material_returns")
    op.drop_table("inv_waste_records")
    op.drop_table("inv_serial_numbers")
    op.drop_table("inv_batch_numbers")
    op.drop_table("inv_item_codes")
    op.drop_table("inv_reorder_levels")
    op.drop_table("inv_stock_reservations")
    op.drop_table("inv_stock_transfers")
    op.drop_table("inv_stock_layers")
    op.drop_table("inv_stock_items")
    op.drop_table("inv_material_items")
    op.drop_table("inv_warehouses")
    op.drop_table("inv_settings")
