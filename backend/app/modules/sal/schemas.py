"""Sales request/response schemas."""
from marshmallow import Schema, fields, validate

from app.modules.sal.models import ORDER_STATUSES


class SalesSettingsSchema(Schema):
    id = fields.UUID(dump_only=True)
    company_id = fields.UUID(required=True)
    receivable_account_id = fields.UUID(required=True)
    revenue_account_id = fields.UUID(required=True)
    vat_account_id = fields.UUID(allow_none=True, load_default=None)
    vat_percent = fields.Decimal(load_default="7.5", as_string=True, validate=validate.Range(min=0, max=100))
    payment_terms_days = fields.Int(load_default=30, validate=validate.Range(min=0, max=365))


class OrderLineInputSchema(Schema):
    material_item_id = fields.UUID(required=True)
    quantity = fields.Decimal(required=True, as_string=True)
    unit_price = fields.Decimal(allow_none=True, load_default=None, as_string=True)


class OrderInputSchema(Schema):
    client_id = fields.UUID(required=True)
    warehouse_id = fields.UUID(required=True)
    order_date = fields.Date(allow_none=True, load_default=None)
    delivery_date = fields.Date(allow_none=True, load_default=None)
    notes = fields.Str(allow_none=True, load_default=None)
    lines = fields.List(fields.Nested(OrderLineInputSchema), required=True)


class DeliveryLineInputSchema(Schema):
    order_line_id = fields.UUID(required=True)
    quantity = fields.Decimal(required=True, as_string=True)


class DeliveryInputSchema(Schema):
    lines = fields.List(fields.Nested(DeliveryLineInputSchema), required=True)
    delivered_at = fields.Date(allow_none=True, load_default=None)
    notes = fields.Str(allow_none=True, load_default=None)


class OrderLineSchema(Schema):
    id = fields.UUID(dump_only=True)
    material_item_id = fields.UUID(dump_only=True)
    quantity = fields.Decimal(dump_only=True, as_string=True)
    unit_price = fields.Decimal(dump_only=True, as_string=True)
    delivered_quantity = fields.Decimal(dump_only=True, as_string=True)
    invoiced_quantity = fields.Decimal(dump_only=True, as_string=True)


class DeliveryLineSchema(Schema):
    order_line_id = fields.UUID(dump_only=True)
    material_item_id = fields.UUID(dump_only=True)
    quantity = fields.Decimal(dump_only=True, as_string=True)
    valued_cost = fields.Decimal(dump_only=True, as_string=True)


class DeliverySchema(Schema):
    id = fields.UUID(dump_only=True)
    number = fields.Str(dump_only=True)
    order_id = fields.UUID(dump_only=True)
    delivered_at = fields.Date(dump_only=True)
    notes = fields.Str(dump_only=True, allow_none=True)
    lines = fields.List(fields.Nested(DeliveryLineSchema), dump_only=True)


class InvoiceLineSchema(Schema):
    order_line_id = fields.UUID(dump_only=True)
    material_item_id = fields.UUID(dump_only=True)
    quantity = fields.Decimal(dump_only=True, as_string=True)
    unit_price = fields.Decimal(dump_only=True, as_string=True)
    line_total = fields.Decimal(dump_only=True, as_string=True)


class InvoiceSchema(Schema):
    id = fields.UUID(dump_only=True)
    number = fields.Str(dump_only=True)
    order_id = fields.UUID(dump_only=True)
    ar_invoice_id = fields.UUID(dump_only=True)
    invoice_date = fields.Date(dump_only=True)
    due_date = fields.Date(dump_only=True, allow_none=True)
    net_amount = fields.Decimal(dump_only=True, as_string=True)
    vat_amount = fields.Decimal(dump_only=True, as_string=True)
    amount = fields.Decimal(dump_only=True, as_string=True)
    lines = fields.List(fields.Nested(InvoiceLineSchema), dump_only=True)


class OrderSchema(Schema):
    id = fields.UUID(dump_only=True)
    number = fields.Str(dump_only=True)
    client_id = fields.UUID(dump_only=True)
    warehouse_id = fields.UUID(dump_only=True)
    status = fields.Str(dump_only=True, validate=validate.OneOf(ORDER_STATUSES))
    order_date = fields.Date(dump_only=True)
    delivery_date = fields.Date(dump_only=True, allow_none=True)
    notes = fields.Str(dump_only=True, allow_none=True)
    vat_percent = fields.Decimal(dump_only=True, as_string=True)
    subtotal = fields.Decimal(dump_only=True, as_string=True)
    vat_amount = fields.Decimal(dump_only=True, as_string=True)
    total = fields.Decimal(dump_only=True, as_string=True)
    lines = fields.List(fields.Nested(OrderLineSchema), dump_only=True)
    deliveries = fields.List(fields.Nested(DeliverySchema), dump_only=True)
    invoices = fields.List(fields.Nested(InvoiceSchema), dump_only=True)
    delivered_value = fields.Method("get_delivered_value", dump_only=True)
    delivered_cost = fields.Method("get_delivered_cost", dump_only=True)
    gross_margin = fields.Method("get_gross_margin", dump_only=True)

    def get_delivered_value(self, order):
        from app.modules.sal import services
        return str(services.delivered_value(order))

    def get_delivered_cost(self, order):
        from app.modules.sal import services
        return str(services.delivered_cost(order))

    def get_gross_margin(self, order):
        from app.modules.sal import services
        return str(services.delivered_value(order) - services.delivered_cost(order))
