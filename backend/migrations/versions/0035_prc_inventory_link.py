"""prc to inventory real integration - material_item_id and warehouse_id

Revision ID: 0035_prc_inventory_link
Revises: 0034_ctm_amendment_status
Create Date: 2026-08-15

Closes a real, stale gap found in a production-hardening audit:
confirm_goods_receipt's own comment said "once Module 8 (Inventory)
exists" -- but Module 8 has existed since early in this build.
Confirming a GRN never actually updated real Inventory stock.

Two nullable columns, both loose references (no FK, matching the
established pattern for boq_item_id/cbs_line_item_id on the same
table) -- PRC still does not depend on Inventory's schema directly
(SRS 3.3 bounded-context discipline), it calls Inventory's own
service function once these are set:

- prc_purchase_order_lines.material_item_id -- which Inventory
  material (if any) this line represents. Nullable because not every
  PO line is a trackable inventory material (services, subcontractor
  labor, etc.).
- prc_goods_receipt_notes.warehouse_id -- which warehouse received the
  goods. Nullable for the same reason; required at the service layer
  (not the DB layer) the moment any line on the GRN has a
  material_item_id set -- see app/modules/prc/services.py.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0035_prc_inventory_link"
down_revision = "0034_ctm_amendment_status"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "prc_purchase_order_lines",
        sa.Column("material_item_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "prc_goods_receipt_notes",
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), nullable=True),
    )


def downgrade():
    op.drop_column("prc_goods_receipt_notes", "warehouse_id")
    op.drop_column("prc_purchase_order_lines", "material_item_id")
