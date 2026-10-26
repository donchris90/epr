"""
Manufacturing (Code: MFG)

Turns raw materials into finished goods: a bill of materials (BOM)
says what a product is made from, a work center is where it is made
(with an hourly labour/overhead rate), and a production order is one
run. Completing a run consumes the components from stock, receives the
finished goods at their real unit cost, and records scrap, yield and
the cost split (materials, labour/overhead, fuel).

Design notes:
  - Items are INV's `MaterialItem` (finished goods and raw materials
    live in one catalog, told apart by `item_type`), so stock, FIFO /
    weighted-average valuation and batches are the existing ones.
  - A BOM is single-level. A semi-finished good is made by its own
    production order and then used as a component of the next BOM, so
    multi-level products work without a recursive explosion.
  - `ProductionComponent` snapshots the quantities a run needs when the
    order is created, so editing the BOM later does not rewrite history.
"""
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin

ORDER_STATUSES = ("draft", "released", "in_progress", "done", "cancelled")


class WorkCenter(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """A line, machine or station. `hourly_rate` is the labour plus
    overhead cost of one hour there. `equipment_id` (optional) links a
    machine or generator so fuel can be issued against it."""

    __tablename__ = "mfg_work_centers"

    code = db.Column(db.String(64), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    hourly_rate = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    equipment_id = db.Column(UUID(as_uuid=True), nullable=True)  # eqp_equipment.id, loose reference
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    __table_args__ = (
        db.UniqueConstraint("tenant_id", "code", name="uq_mfg_work_centers_tenant_code"),
        db.CheckConstraint("hourly_rate >= 0", name="ck_mfg_work_centers_rate"),
    )


class Bom(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """Bill of materials: the components needed to make `output_quantity`
    of the product."""

    __tablename__ = "mfg_boms"

    code = db.Column(db.String(64), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    product_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_material_items.id"), nullable=False, index=True)
    output_quantity = db.Column(db.Numeric(18, 4), nullable=False, default=1)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    lines = relationship("BomLine", back_populates="bom", cascade="all, delete-orphan", order_by="BomLine.created_at")

    __table_args__ = (
        db.UniqueConstraint("tenant_id", "code", name="uq_mfg_boms_tenant_code"),
        db.CheckConstraint("output_quantity > 0", name="ck_mfg_boms_output_positive"),
    )


class BomLine(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """`quantity` of the component per `Bom.output_quantity`;
    `scrap_percent` is the expected loss on top of it."""

    __tablename__ = "mfg_bom_lines"

    bom_id = db.Column(UUID(as_uuid=True), db.ForeignKey("mfg_boms.id", ondelete="CASCADE"), nullable=False, index=True)
    component_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_material_items.id"), nullable=False)
    quantity = db.Column(db.Numeric(18, 4), nullable=False)
    scrap_percent = db.Column(db.Numeric(7, 3), nullable=False, default=0)

    bom = relationship("Bom", back_populates="lines")

    __table_args__ = (
        db.UniqueConstraint("bom_id", "component_item_id", name="uq_mfg_bom_lines_bom_component"),
        db.CheckConstraint("quantity > 0", name="ck_mfg_bom_lines_qty_positive"),
        db.CheckConstraint("scrap_percent >= 0 AND scrap_percent < 100", name="ck_mfg_bom_lines_scrap_range"),
    )


class ProductionOrder(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    __tablename__ = "mfg_production_orders"

    number = db.Column(db.String(32), nullable=False)
    bom_id = db.Column(UUID(as_uuid=True), db.ForeignKey("mfg_boms.id"), nullable=False, index=True)
    product_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_material_items.id"), nullable=False)
    warehouse_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_warehouses.id"), nullable=False)
    work_center_id = db.Column(UUID(as_uuid=True), db.ForeignKey("mfg_work_centers.id"), nullable=True)

    status = db.Column(db.String(16), nullable=False, default="draft")
    quantity_planned = db.Column(db.Numeric(18, 4), nullable=False)
    quantity_produced = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    quantity_scrapped = db.Column(db.Numeric(18, 4), nullable=False, default=0)

    planned_start = db.Column(db.Date, nullable=True)
    started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    labour_hours = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    fuel_litres = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    material_cost = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    labour_cost = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    fuel_cost = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    total_cost = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    unit_cost = db.Column(db.Numeric(18, 4), nullable=False, default=0)

    batch_id = db.Column(UUID(as_uuid=True), nullable=True)  # inv_batch_numbers.id of the finished-goods batch
    notes = db.Column(db.Text, nullable=True)

    components = relationship(
        "ProductionComponent", back_populates="order", cascade="all, delete-orphan", order_by="ProductionComponent.created_at"
    )

    __table_args__ = (
        db.UniqueConstraint("tenant_id", "number", name="uq_mfg_production_orders_tenant_number"),
        db.CheckConstraint(f"status IN {ORDER_STATUSES}", name="ck_mfg_production_orders_status"),
        db.CheckConstraint("quantity_planned > 0", name="ck_mfg_production_orders_planned_positive"),
    )


class ProductionComponent(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """One component of one run: what the BOM said it needs
    (`planned_quantity`) against what was actually drawn from stock."""

    __tablename__ = "mfg_production_components"

    order_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("mfg_production_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    component_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_material_items.id"), nullable=False)
    planned_quantity = db.Column(db.Numeric(18, 4), nullable=False)
    consumed_quantity = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    valued_cost = db.Column(db.Numeric(18, 4), nullable=False, default=0)

    order = relationship("ProductionOrder", back_populates="components")
