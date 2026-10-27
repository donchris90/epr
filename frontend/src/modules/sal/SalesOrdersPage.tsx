import { useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input, Field, ErrorBanner, formatMoney } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import { useClients } from "../bdc/hooks";
import { useMaterialItems, useWarehouses } from "../inv/hooks";
import { useCreateSalesOrder, useDeliver, useSalesOrderAction, useSalesOrders, type SalesOrder, type SalesStatus } from "./hooks";

const selectStyle = { padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, background: "#fff" };
const STATUS_TONE: Record<SalesStatus, "neutral" | "amber" | "steel" | "green" | "brick"> = {
  draft: "neutral",
  confirmed: "steel",
  partially_delivered: "amber",
  delivered: "green",
  cancelled: "brick",
};
const emptyLine = { material_item_id: "", quantity: "", unit_price: "" };
const num = (v: string) => Number(v);

function DeliverPanel({ order, itemCode, onClose }: { order: SalesOrder; itemCode: (id: string) => string; onClose: () => void }) {
  const deliver = useDeliver();
  const open = order.lines.filter((l) => num(l.quantity) > num(l.delivered_quantity));
  const [qty, setQty] = useState<Record<string, string>>(
    Object.fromEntries(open.map((l) => [l.id, String(num(l.quantity) - num(l.delivered_quantity))])),
  );
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const lines = open.filter((l) => num(qty[l.id] || "0") > 0).map((l) => ({ order_line_id: l.id, quantity: qty[l.id] }));
    if (!lines.length) {
      setError("Enter a quantity for at least one line.");
      return;
    }
    try {
      await deliver.mutateAsync({ id: order.id, lines });
      onClose();
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <Card style={{ marginBottom: 20 }}>
      <h3 style={{ fontSize: 14, marginBottom: 4 }}>Deliver {order.number}</h3>
      <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
        Goods are taken out of the warehouse now. If any item is short, nothing is delivered.
      </p>
      {error && <ErrorBanner title="Couldn't deliver" detail={error} onDismiss={() => setError(null)} />}
      <form onSubmit={submit}>
        {open.map((l) => (
          <div key={l.id} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "3fr 1fr", gap: 8, marginBottom: 8, alignItems: "end" }}>
            <Field label={`${itemCode(l.material_item_id)} — ${num(l.quantity) - num(l.delivered_quantity)} left to deliver`}>
              <Input
                inputMode="decimal"
                aria-label={`Deliver ${itemCode(l.material_item_id)}`}
                value={qty[l.id]}
                onChange={(e) => setQty({ ...qty, [l.id]: e.target.value })}
              />
            </Field>
          </div>
        ))}
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <Button type="submit" disabled={deliver.isPending}>Confirm delivery</Button>
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
        </div>
      </form>
    </Card>
  );
}

function OrderDetail({ order, itemCode }: { order: SalesOrder; itemCode: (id: string) => string }) {
  return (
    <Card style={{ marginBottom: 20 }}>
      <h3 style={{ fontSize: 14, marginBottom: 8 }}>{order.number}</h3>
      <Table ariaLabel="Order lines">
        <thead>
          <tr><Th>Item</Th><Th>Ordered</Th><Th>Price</Th><Th>Delivered</Th><Th>Invoiced</Th></tr>
        </thead>
        <tbody>
          {order.lines.map((l) => (
            <tr key={l.id}>
              <Td mono>{itemCode(l.material_item_id)}</Td>
              <Td mono>{num(l.quantity)}</Td>
              <Td mono>{formatMoney(l.unit_price)}</Td>
              <Td mono>{num(l.delivered_quantity)}</Td>
              <Td mono>{num(l.invoiced_quantity)}</Td>
            </tr>
          ))}
        </tbody>
      </Table>
      <p style={{ fontSize: 12, margin: "12px 0 4px" }}>
        Subtotal {formatMoney(order.subtotal)} + VAT ({num(order.vat_percent)}%) {formatMoney(order.vat_amount)} = <strong>{formatMoney(order.total)}</strong>
      </p>
      {order.deliveries.length > 0 && (
        <p style={{ fontSize: 12, marginBottom: 4 }}>
          Delivery notes:{" "}
          {order.deliveries.map((d) => (
            <Link key={d.id} to={`/sales/print/${order.id}/delivery/${d.id}`} style={{ marginRight: 6 }}>{d.number}</Link>
          ))}
          Delivered goods are worth {formatMoney(order.delivered_value)} against a stock cost of{" "}
          {formatMoney(order.delivered_cost)} — margin <strong>{formatMoney(order.gross_margin)}</strong>.
        </p>
      )}
      {order.invoices.length > 0 && (
        <p style={{ fontSize: 12 }}>
          Invoices:{" "}
          {order.invoices.map((i) => (
            <Link key={i.id} to={`/sales/print/${order.id}/invoice/${i.id}`} style={{ marginRight: 6 }}>{`${i.number} (${formatMoney(i.amount)})`}</Link>
          ))}
        </p>
      )}
    </Card>
  );
}

export default function SalesOrdersPage() {
  const { data: orders, isLoading } = useSalesOrders();
  const { data: clients } = useClients();
  const { data: warehouses } = useWarehouses();
  const { data: items } = useMaterialItems();
  const create = useCreateSalesOrder();
  const action = useSalesOrderAction();

  const [show, setShow] = useState(false);
  const [head, setHead] = useState({ client_id: "", warehouse_id: "" });
  const [lines, setLines] = useState([{ ...emptyLine }]);
  const [delivering, setDelivering] = useState<SalesOrder | null>(null);
  const [viewing, setViewing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const itemCode = (id: string) => items?.find((i: any) => i.id === id)?.code ?? "Unknown item";
  const clientName = (id: string) => clients?.find((c) => c.id === id)?.name ?? "Unknown client";
  const viewed = orders?.find((o) => o.id === viewing) ?? null;
  const setLine = (idx: number, patch: Partial<typeof emptyLine>) => setLines((ls) => ls.map((l, i) => (i === idx ? { ...l, ...patch } : l)));

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await create.mutateAsync({
        ...head,
        lines: lines.map((l) => ({ material_item_id: l.material_item_id, quantity: l.quantity, unit_price: l.unit_price || null })),
      });
      setHead({ client_id: "", warehouse_id: "" });
      setLines([{ ...emptyLine }]);
      setShow(false);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  async function run(id: string, act: "confirm" | "cancel" | "invoice") {
    setError(null);
    try {
      await action.mutateAsync({ id, action: act });
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Sales"
        title="Sales orders"
        action={<Button onClick={() => setShow((v) => !v)}>{show ? "Cancel" : "New sales order"}</Button>}
      />
      {error && <ErrorBanner title="Couldn't update the order" detail={error} onDismiss={() => setError(null)} />}

      {show && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreate}>
            <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
              <Field label="Client">
                <select aria-label="Client" required value={head.client_id} onChange={(e) => setHead({ ...head, client_id: e.target.value })} style={selectStyle}>
                  <option value="">Select client…</option>
                  {clients?.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </Field>
              <Field label="Ship from warehouse">
                <select aria-label="Warehouse" required value={head.warehouse_id} onChange={(e) => setHead({ ...head, warehouse_id: e.target.value })} style={selectStyle}>
                  <option value="">Select warehouse…</option>
                  {warehouses?.map((w) => (
                    <option key={w.id} value={w.id}>{w.name}</option>
                  ))}
                </select>
              </Field>
            </div>
            <h3 style={{ fontSize: 13, marginBottom: 8 }}>Items</h3>
            {lines.map((line, idx) => (
              <div key={idx} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "3fr 1fr 1fr auto", gap: 8, marginBottom: 8 }}>
                <select
                  required
                  aria-label={`Item ${idx + 1}`}
                  value={line.material_item_id}
                  onChange={(e) => setLine(idx, { material_item_id: e.target.value })}
                  style={selectStyle}
                >
                  <option value="">Select item…</option>
                  {items?.map((i: any) => (
                    <option key={i.id} value={i.id}>{i.code} — {i.description}</option>
                  ))}
                </select>
                <Input required inputMode="decimal" aria-label={`Quantity ${idx + 1}`} placeholder="Quantity" value={line.quantity} onChange={(e) => setLine(idx, { quantity: e.target.value })} />
                <Input inputMode="decimal" aria-label={`Price ${idx + 1}`} placeholder="Unit price (item default)" value={line.unit_price} onChange={(e) => setLine(idx, { unit_price: e.target.value })} />
                <Button type="button" variant="ghost" disabled={lines.length === 1} onClick={() => setLines((ls) => ls.filter((_, i) => i !== idx))}>Remove</Button>
              </div>
            ))}
            <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <Button type="button" variant="secondary" onClick={() => setLines((ls) => [...ls, { ...emptyLine }])}>Add item</Button>
              <Button type="submit" disabled={create.isPending}>Save order</Button>
            </div>
          </form>
        </Card>
      )}

      {delivering && <DeliverPanel order={delivering} itemCode={itemCode} onClose={() => setDelivering(null)} />}
      {viewed && <OrderDetail order={viewed} itemCode={itemCode} />}

      {isLoading ? null : !orders?.length ? (
        <EmptyState title="No sales orders yet" hint="Record an order for a client, deliver the goods from stock, then invoice what has gone out." />
      ) : (
        <Card>
          <Table ariaLabel="Sales orders">
            <thead>
              <tr><Th>Order</Th><Th>Client</Th><Th>Date</Th><Th>Total</Th><Th>Status</Th><Th></Th></tr>
            </thead>
            <tbody>
              {orders.map((o) => {
                const toInvoice = o.lines.some((l) => num(l.delivered_quantity) > num(l.invoiced_quantity));
                return (
                  <tr key={o.id}>
                    <Td mono>{o.number}</Td>
                    <Td>{clientName(o.client_id)}</Td>
                    <Td mono>{o.order_date}</Td>
                    <Td mono>{formatMoney(o.total)}</Td>
                    <Td><Badge tone={STATUS_TONE[o.status]}>{o.status.replace("_", " ")}</Badge></Td>
                    <Td>
                      <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                        {o.status === "draft" && <Button variant="secondary" onClick={() => run(o.id, "confirm")}>Confirm</Button>}
                        {(o.status === "confirmed" || o.status === "partially_delivered") && <Button onClick={() => setDelivering(o)}>Deliver</Button>}
                        {toInvoice && <Button variant="secondary" onClick={() => run(o.id, "invoice")}>Invoice</Button>}
                        {o.status !== "cancelled" && <Button variant="ghost" onClick={() => setViewing(viewing === o.id ? null : o.id)}>{viewing === o.id ? "Hide" : "Details"}</Button>}
                        {(o.status === "draft" || o.status === "confirmed") && <Button variant="ghost" onClick={() => run(o.id, "cancel")}>Cancel</Button>}
                      </div>
                    </Td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        </Card>
      )}
    </div>
  );
}
