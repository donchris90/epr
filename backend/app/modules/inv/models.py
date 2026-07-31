"""
Module 8 — Inventory & Warehouse (Code: INV)
SRS Section 4.8.

Tracks every material movement across the company's central yard,
site stores, and quarries, with batch/serial/barcode granularity.

Key Data Entities (SRS 4.8): Warehouse, StockItem, StockTransfer,
StockReservation, ReorderLevel, Barcode, QRCode, BatchNumber,
SerialNumber, WasteRecord, MaterialReturn.

Design notes:
  - `MaterialItem` (the catalog/master item) is not in the SRS's named
    entity list but is the natural home for a stable identity that
    `StockItem` (a per-warehouse balance), `BatchNumber`, `SerialNumber`,
    and `ItemCode` (Barcode/QRCode, consolidated -- see below) all need
    to reference, the same way EST's CostLibraryItem underlies its
    per-rate-analysis lines.
  - `Barcode` and `QRCode` share an identical shape (a code value
    attached to a material item), so they're one table, `ItemCode`,
    discriminated by `code_type` -- the same pattern used for EST's
    ContingencyItem and EXE's SiteMedia.
  - `StockLayer` is not in the SRS's named entity list either, but is
    what makes FIFO valuation (INV-11) real rather than a label with no
    behavior behind it -- each receipt creates a layer; issues consume
    the oldest layers first. Weighted-average valuation doesn't need
    layers (see StockItem.average_unit_cost), so this table is only
    populated when the tenant's InventorySettings.valuation_method is
    "fifo".
"""
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin


WAREHOUSE_TYPES = ("central_yard", "site_store", "quarry")
TRANSFER_STATUSES = ("in_transit", "received")
RESERVATION_STATUSES = ("active", "released", "consumed")
CODE_TYPES = ("barcode", "qr")
WASTE_CAUSES = ("breakage", "theft", "spoilage", "over_order")
RETURN_TYPES = ("site_to_yard", "to_vendor")
RETURN_CONDITIONS = ("good", "damaged")
RETURN_STATUSES = ("pending", "completed")
VALUATION_METHODS = ("weighted_average", "fifo")
SERIAL_STATUSES = ("in_stock", "issued", "disposed")
COUNT_TYPES = ("cycle", "full")
COUNT_STATUSES = ("draft", "completed", "adjusted")


class InventorySettings(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """INV-11: valuation method is a tenant-wide setting, consistent
    across every warehouse -- not configurable per warehouse, per the
    SRS's own wording."""

    __tablename__ = "inv_settings"

    valuation_method = db.Column(db.String(16), nullable=False, default="weighted_average")

    __table_args__ = (
        db.CheckConstraint(f"valuation_method IN {VALUATION_METHODS}", name="ck_inv_settings_valuation_method"),
        db.UniqueConstraint("tenant_id", name="uq_inv_settings_tenant"),
    )


class Warehouse(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """INV-01: Central Yard, Site Store, or Quarry, each with
    independent balances rolled up to a company-wide view."""

    __tablename__ = "inv_warehouses"

    name = db.Column(db.String(255), nullable=False)
    warehouse_type = db.Column(db.String(16), nullable=False)
    project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)  # for site stores
    location = db.Column(db.String(255), nullable=True)

    __table_args__ = (db.CheckConstraint(f"warehouse_type IN {WAREHOUSE_TYPES}", name="ck_inv_warehouses_type"),)


class MaterialItem(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """The catalog identity underlying StockItem balances, batches,
    serials, and codes -- see module docstring."""

    __tablename__ = "inv_material_items"

    code = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text, nullable=False)
    unit = db.Column(db.String(32), nullable=True)
    is_batch_tracked = db.Column(db.Boolean, nullable=False, default=False)  # INV-06
    is_serial_tracked = db.Column(db.Boolean, nullable=False, default=False)  # INV-07

    __table_args__ = (db.UniqueConstraint("tenant_id", "code", name="uq_inv_material_items_tenant_code"),)


class StockItem(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """INV-01: a per-warehouse stock balance for one material item.
    `average_unit_cost` is maintained for weighted-average valuation;
    under FIFO valuation it is informational only (see StockLayer for
    the source of truth)."""

    __tablename__ = "inv_stock_items"

    warehouse_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_warehouses.id"), nullable=False, index=True)
    material_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_material_items.id"), nullable=False, index=True)

    quantity_on_hand = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    average_unit_cost = db.Column(db.Numeric(18, 4), nullable=False, default=0)

    __table_args__ = (
        db.CheckConstraint("quantity_on_hand >= 0", name="ck_inv_stock_items_qty_non_negative"),
        db.UniqueConstraint("warehouse_id", "material_item_id", name="uq_inv_stock_items_warehouse_material"),
    )


class StockLayer(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """FIFO valuation layers -- one per receipt, consumed oldest-first
    on issue. Only populated when the tenant's valuation method is
    "fifo" (see services.receive_stock / issue_stock)."""

    __tablename__ = "inv_stock_layers"

    warehouse_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_warehouses.id"), nullable=False, index=True)
    material_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_material_items.id"), nullable=False, index=True)

    received_at = db.Column(db.DateTime(timezone=True), nullable=False)
    quantity_remaining = db.Column(db.Numeric(18, 4), nullable=False)
    unit_cost = db.Column(db.Numeric(18, 4), nullable=False)

    __table_args__ = (db.CheckConstraint("quantity_remaining >= 0", name="ck_inv_stock_layers_qty_non_negative"),)


class StockTransfer(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """INV-02: transfer between warehouses. Business rule: not
    complete, and does NOT update destination balances, until receipt
    is confirmed at the destination (SRS 4.8)."""

    __tablename__ = "inv_stock_transfers"

    from_warehouse_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_warehouses.id"), nullable=False, index=True)
    to_warehouse_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_warehouses.id"), nullable=False, index=True)
    material_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_material_items.id"), nullable=False, index=True)

    quantity = db.Column(db.Numeric(18, 4), nullable=False)
    status = db.Column(db.String(16), nullable=False, default="in_transit")
    dispatched_at = db.Column(db.DateTime(timezone=True), nullable=True)
    dispatched_by = db.Column(UUID(as_uuid=True), nullable=True)
    received_at = db.Column(db.DateTime(timezone=True), nullable=True)
    received_by = db.Column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        db.CheckConstraint(f"status IN {TRANSFER_STATUSES}", name="ck_inv_stock_transfers_status"),
        db.CheckConstraint("from_warehouse_id != to_warehouse_id", name="ck_inv_stock_transfers_diff_warehouses"),
    )


class StockReservation(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """INV-03: reduces available (not physical) quantity shown to
    other projects."""

    __tablename__ = "inv_stock_reservations"

    warehouse_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_warehouses.id"), nullable=False, index=True)
    material_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_material_items.id"), nullable=False, index=True)
    project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)
    activity_id = db.Column(UUID(as_uuid=True), nullable=True)  # pln_activities.id, loose reference

    quantity = db.Column(db.Numeric(18, 4), nullable=False)
    status = db.Column(db.String(16), nullable=False, default="active")
    reserved_by = db.Column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (db.CheckConstraint(f"status IN {RESERVATION_STATUSES}", name="ck_inv_stock_reservations_status"),)


class ReorderLevel(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """INV-04: configurable per item per warehouse."""

    __tablename__ = "inv_reorder_levels"

    warehouse_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_warehouses.id"), nullable=False, index=True)
    material_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_material_items.id"), nullable=False, index=True)

    reorder_point = db.Column(db.Numeric(18, 4), nullable=False)
    reorder_quantity = db.Column(db.Numeric(18, 4), nullable=False)
    auto_create_pr = db.Column(db.Boolean, nullable=False, default=False)
    # Set by app/modules/inv/tasks.py whenever it auto-creates a draft
    # PR from this row -- read back by the same task to avoid creating
    # a new PR every single run while the shortage persists.
    last_auto_pr_at = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        db.UniqueConstraint("warehouse_id", "material_item_id", name="uq_inv_reorder_levels_warehouse_material"),
    )


class ItemCode(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """INV-05: Barcode and QR Code, consolidated -- see module
    docstring."""

    __tablename__ = "inv_item_codes"

    material_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_material_items.id"), nullable=False, index=True)
    code_type = db.Column(db.String(8), nullable=False)
    code_value = db.Column(db.String(128), nullable=False)

    __table_args__ = (
        db.CheckConstraint(f"code_type IN {CODE_TYPES}", name="ck_inv_item_codes_type"),
        db.UniqueConstraint("tenant_id", "code_value", name="uq_inv_item_codes_tenant_value"),
    )


class BatchNumber(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """INV-06: shelf-life / quality-certificate tracked materials."""

    __tablename__ = "inv_batch_numbers"

    material_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_material_items.id"), nullable=False, index=True)
    warehouse_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_warehouses.id"), nullable=False, index=True)

    batch_number = db.Column(db.String(128), nullable=False)
    manufactured_date = db.Column(db.Date, nullable=True)
    expiry_date = db.Column(db.Date, nullable=True, index=True)
    quality_cert_document_id = db.Column(UUID(as_uuid=True), db.ForeignKey("documents.id"), nullable=True)
    quantity_remaining = db.Column(db.Numeric(18, 4), nullable=False, default=0)


class SerialNumber(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """INV-07: high-value individually trackable items."""

    __tablename__ = "inv_serial_numbers"

    material_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_material_items.id"), nullable=False, index=True)
    serial_number = db.Column(db.String(128), nullable=False)
    current_warehouse_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_warehouses.id"), nullable=True)
    status = db.Column(db.String(16), nullable=False, default="in_stock")

    __table_args__ = (
        db.CheckConstraint(f"status IN {SERIAL_STATUSES}", name="ck_inv_serial_numbers_status"),
        db.UniqueConstraint("tenant_id", "serial_number", name="uq_inv_serial_numbers_tenant_serial"),
    )


class WasteRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """INV-08: material loss with cause classification. Business rule:
    rolls up into Module 19's project cost variance as a distinct cost
    category, never hidden inside standard consumption -- this table
    is that distinct category's source of truth."""

    __tablename__ = "inv_waste_records"

    warehouse_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_warehouses.id"), nullable=False, index=True)
    material_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_material_items.id"), nullable=False, index=True)
    project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)

    quantity = db.Column(db.Numeric(18, 4), nullable=False)
    cause_classification = db.Column(db.String(16), nullable=False)
    recorded_at = db.Column(db.DateTime(timezone=True), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # The valued cost of the waste, computed at record time from the
    # warehouse's current valuation (weighted-average cost or FIFO
    # layer consumption) -- this is the actual number that rolls up
    # into Module 19, not just the quantity.
    valued_cost = db.Column(db.Numeric(18, 4), nullable=True)

    __table_args__ = (db.CheckConstraint(f"cause_classification IN {WASTE_CAUSES}", name="ck_inv_waste_records_cause"),)


class MaterialReturn(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """INV-09: site-to-yard or to-vendor returns, with condition and
    optional credit-note linkage to Module 7/17."""

    __tablename__ = "inv_material_returns"

    material_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_material_items.id"), nullable=False, index=True)
    source_warehouse_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_warehouses.id"), nullable=False)
    destination_warehouse_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_warehouses.id"), nullable=True)
    vendor_id = db.Column(UUID(as_uuid=True), nullable=True)  # prc_vendors.id, loose reference

    quantity = db.Column(db.Numeric(18, 4), nullable=False)
    return_type = db.Column(db.String(16), nullable=False)
    condition = db.Column(db.String(16), nullable=False, default="good")
    credit_note_reference = db.Column(db.String(128), nullable=True)
    status = db.Column(db.String(16), nullable=False, default="pending")

    __table_args__ = (
        db.CheckConstraint(f"return_type IN {RETURN_TYPES}", name="ck_inv_material_returns_type"),
        db.CheckConstraint(f"condition IN {RETURN_CONDITIONS}", name="ck_inv_material_returns_condition"),
        db.CheckConstraint(f"status IN {RETURN_STATUSES}", name="ck_inv_material_returns_status"),
    )


class StockCount(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """INV-10: cycle count or full stock take, with variance reporting
    against system-recorded balances."""

    __tablename__ = "inv_stock_counts"

    warehouse_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_warehouses.id"), nullable=False, index=True)
    count_type = db.Column(db.String(8), nullable=False)
    status = db.Column(db.String(16), nullable=False, default="draft")
    counted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    counted_by = db.Column(UUID(as_uuid=True), nullable=True)

    lines = relationship("StockCountLine", back_populates="stock_count", cascade="all, delete-orphan")

    __table_args__ = (
        db.CheckConstraint(f"count_type IN {COUNT_TYPES}", name="ck_inv_stock_counts_type"),
        db.CheckConstraint(f"status IN {COUNT_STATUSES}", name="ck_inv_stock_counts_status"),
    )


class StockCountLine(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    __tablename__ = "inv_stock_count_lines"

    stock_count_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_stock_counts.id"), nullable=False, index=True)
    material_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_material_items.id"), nullable=False, index=True)

    system_quantity = db.Column(db.Numeric(18, 4), nullable=False)  # snapshot at count time
    counted_quantity = db.Column(db.Numeric(18, 4), nullable=True)

    stock_count = relationship("StockCount", back_populates="lines")

    @property
    def variance(self):
        if self.counted_quantity is None:
            return None
        return self.counted_quantity - self.system_quantity
