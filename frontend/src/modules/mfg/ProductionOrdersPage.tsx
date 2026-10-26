import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input, Field, ErrorBanner, formatMoney } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import { useMaterialItems, useWarehouses } from "../inv/hooks";
import {
  useAvailability,
  useBoms,
  useCompleteOrder,
  useCreateOrder,
  useOrderAction,
  useProductionOrders,
  useVariances,
  useWorkCenters,
  type OrderStatus,
  type ProductionOrder,
} from "./hooks";

const selectStyle = { padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, background: "#fff" };
const STATUS_TONE: Record<OrderStatus, "neutral" | "amber" | "steel" | "green" | "brick"> = {
  draft: "neutral",
  released: "steel",
  in_progress: "amber",
  done: "green",
  cancelled: "brick",
};

const num = (v: string) => Number(v);

function CompletePanel({ order, onClose }: { order: ProductionOrder; onClose: () => void }) {
  const complete = useCompleteOrder();
  const { data: availability } = useAvailability(order.id);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    quantity_produced: String(num(order.quantity_planned)),
    quantity_scrapped: "0",
    labour_hours: "0",
    fuel_litres: "0",
    fuel_unit_cost: "",
    batch_number: "",
    expiry_date: "",
    quarantine: false,
  });
  const shortages = availability?.filter((a) => num(a.short) > 0) ?? [];
  const fuel = num(form.fuel_litres) > 0;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await complete.mutateAsync({
        id: order.id,
        quantity_produced: form.quantity_produced,
        quantity_scrapped: form.quantity_scrapped || "0",
        labour_hours: form.labour_hours || "0",
        fuel_litres: form.fuel_litres || "0",
        fuel_unit_cost: fuel ? form.fuel_unit_cost : null,
        batch_number: form.batch_number || null,
        expiry_date: form.expiry_date || null,
        quarantine: form.quarantine,
      });
      onClose();
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <Card style={{ marginBottom: 20 }}>
      <h3 style={{ fontSize: 14, marginBottom: 4 }}>Complete {order.number}</h3>
      <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
        Components are taken from stock at the quantity the recipe says for what you actually ran, and the finished goods are added to stock at the real cost.
      </p>
      {shortages.length > 0 && (
        <ErrorBanner
          title="Not enough stock for the planned run"
          detail={shortages.map((s) => `${s.code}: short by ${num(s.short)}`).join("; ")}
        />
      )}
      {error && <ErrorBanner title="Couldn't complete the order" detail={error} onDismiss={() => setError(null)} />}
      <form onSubmit={submit}>
        <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 12 }}>
          <Field label="Good units produced">
            <Input required inputMode="decimal" value={form.quantity_produced} onChange={(e) => setForm({ ...form, quantity_produced: e.target.value })} />
          </Field>
          <Field label="Scrapped units">
            <Input inputMode="decimal" value={form.quantity_scrapped} onChange={(e) => setForm({ ...form, quantity_scrapped: e.target.value })} />
          </Field>
          <Field label="Labour hours">
            <Input inputMode="decimal" value={form.labour_hours} onChange={(e) => setForm({ ...form, labour_hours: e.target.value })} />
          </Field>
          <Field label="Fuel used (litres)">
            <Input inputMode="decimal" value={form.fuel_litres} onChange={(e) => setForm({ ...form, fuel_litres: e.target.value })} />
          </Field>
          {fuel && (
            <Field label="Fuel price per litre" hint="Counted in the cost of this run.">
              <Input required inputMode="decimal" value={form.fuel_unit_cost} onChange={(e) => setForm({ ...form, fuel_unit_cost: e.target.value })} />
            </Field>
          )}
          <Field label="Batch number" hint="Required for batch-tracked products.">
            <Input value={form.batch_number} onChange={(e) => setForm({ ...form, batch_number: e.target.value })} />
          </Field>
          <Field label="Expiry date">
            <Input type="date" value={form.expiry_date} onChange={(e) => setForm({ ...form, expiry_date: e.target.value })} />
          </Field>
        </div>
        <label style={{ display: "flex", gap: 6, fontSize: 12, marginBottom: 12 }}>
          <input type="checkbox" checked={form.quarantine} onChange={(e) => setForm({ ...form, quarantine: e.target.checked })} />
          Hold this batch in quarantine until quality releases it
        </label>
        <div style={{ display: "flex", gap: 8 }}>
          <Button type="submit" disabled={complete.isPending}>Complete order</Button>
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
        </div>
      </form>
    </Card>
  );
}

function CostDetail({ order, itemCode }: { order: ProductionOrder; itemCode: (id: string) => string }) {
  const { data: variances } = useVariances(order.id);
  return (
    <Card style={{ marginBottom: 20 }}>
      <h3 style={{ fontSize: 14, marginBottom: 8 }}>{order.number} — cost</h3>
      <Table ariaLabel="Cost breakdown">
        <tbody>
          <tr><Td>Materials</Td><Td mono>{formatMoney(order.material_cost)}</Td></tr>
          <tr><Td>Labour and overhead ({num(order.labour_hours)} h)</Td><Td mono>{formatMoney(order.labour_cost)}</Td></tr>
          <tr><Td>Fuel ({num(order.fuel_litres)} L)</Td><Td mono>{formatMoney(order.fuel_cost)}</Td></tr>
          <tr><Td><strong>Total</strong></Td><Td mono><strong>{formatMoney(order.total_cost)}</strong></Td></tr>
          <tr><Td>Cost per good unit</Td><Td mono>{formatMoney(order.unit_cost)}</Td></tr>
        </tbody>
      </Table>
      {!!variances?.length && (
        <>
          <h4 style={{ fontSize: 13, margin: "16px 0 8px" }}>Material use against the recipe</h4>
          <Table ariaLabel="Material variances">
            <thead>
              <tr><Th>Component</Th><Th>Expected</Th><Th>Used</Th><Th>Difference</Th></tr>
            </thead>
            <tbody>
              {variances.map((v) => (
                <tr key={v.component_item_id}>
                  <Td mono>{itemCode(v.component_item_id)}</Td>
                  <Td mono>{num(v.planned)}</Td>
                  <Td mono>{num(v.consumed)}</Td>
                  <Td mono>{num(v.variance) > 0 ? <Badge tone="brick">+{num(v.variance)}</Badge> : num(v.variance)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </>
      )}
    </Card>
  );
}

export default function ProductionOrdersPage() {
  const { data: orders, isLoading } = useProductionOrders();
  const { data: boms } = useBoms();
  const { data: warehouses } = useWarehouses();
  const { data: centers } = useWorkCenters();
  const { data: items } = useMaterialItems();
  const createOrder = useCreateOrder();
  const action = useOrderAction();

  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ bom_id: "", quantity: "", warehouse_id: "", work_center_id: "" });
  const [completing, setCompleting] = useState<ProductionOrder | null>(null);
  const [viewing, setViewing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const itemCode = (id: string) => items?.find((i) => i.id === id)?.code ?? "Unknown item";
  const viewed = orders?.find((o) => o.id === viewing) ?? null;

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createOrder.mutateAsync({ ...form, work_center_id: form.work_center_id || null });
      setForm({ bom_id: "", quantity: "", warehouse_id: "", work_center_id: "" });
      setShow(false);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  async function run(id: string, act: "release" | "start" | "cancel") {
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
        eyebrow="Manufacturing"
        title="Production orders"
        action={<Button onClick={() => setShow((v) => !v)}>{show ? "Cancel" : "New production order"}</Button>}
      />
      {error && <ErrorBanner title="Couldn't update the order" detail={error} onDismiss={() => setError(null)} />}

      {show && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreate} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr 2fr 2fr auto", gap: 12 }}>
            <Field label="Bill of materials">
              <select required value={form.bom_id} onChange={(e) => setForm({ ...form, bom_id: e.target.value })} style={selectStyle}>
                <option value="">Select BOM…</option>
                {boms?.filter((b) => b.is_active).map((b) => (
                  <option key={b.id} value={b.id}>{b.code} — {b.name}</option>
                ))}
              </select>
            </Field>
            <Field label="Quantity">
              <Input required inputMode="decimal" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
            </Field>
            <Field label="Warehouse">
              <select required value={form.warehouse_id} onChange={(e) => setForm({ ...form, warehouse_id: e.target.value })} style={selectStyle}>
                <option value="">Select warehouse…</option>
                {warehouses?.map((w) => (
                  <option key={w.id} value={w.id}>{w.name}</option>
                ))}
              </select>
            </Field>
            <Field label="Work center (optional)">
              <select value={form.work_center_id} onChange={(e) => setForm({ ...form, work_center_id: e.target.value })} style={selectStyle}>
                <option value="">None</option>
                {centers?.filter((c) => c.is_active).map((c) => (
                  <option key={c.id} value={c.id}>{c.code} — {c.name}</option>
                ))}
              </select>
            </Field>
            <Button type="submit" disabled={createOrder.isPending} style={{ height: 38, alignSelf: "end" }}>Create</Button>
          </form>
        </Card>
      )}

      {completing && <CompletePanel order={completing} onClose={() => setCompleting(null)} />}
      {viewed && <CostDetail order={viewed} itemCode={itemCode} />}

      {isLoading ? null : !orders?.length ? (
        <EmptyState title="No production orders yet" hint="Create a BOM, then plan a run here. Completing a run uses up the components and adds the finished goods to stock." />
      ) : (
        <Card>
          <Table ariaLabel="Production orders">
            <thead>
              <tr><Th>Order</Th><Th>Product</Th><Th>Planned</Th><Th>Produced</Th><Th>Status</Th><Th>Unit cost</Th><Th></Th></tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id}>
                  <Td mono>{o.number}</Td>
                  <Td mono>{itemCode(o.product_item_id)}</Td>
                  <Td mono>{num(o.quantity_planned)}</Td>
                  <Td mono>{o.status === "done" ? num(o.quantity_produced) : "—"}</Td>
                  <Td><Badge tone={STATUS_TONE[o.status]}>{o.status.replace("_", " ")}</Badge></Td>
                  <Td mono>{o.status === "done" ? formatMoney(o.unit_cost) : "—"}</Td>
                  <Td>
                    <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                      {o.status === "draft" && <Button variant="secondary" onClick={() => run(o.id, "release")}>Release</Button>}
                      {o.status === "released" && <Button variant="secondary" onClick={() => run(o.id, "start")}>Start</Button>}
                      {o.status === "in_progress" && <Button onClick={() => setCompleting(o)}>Complete</Button>}
                      {o.status === "done" && (
                        <Button variant="ghost" onClick={() => setViewing(viewing === o.id ? null : o.id)}>
                          {viewing === o.id ? "Hide cost" : "View cost"}
                        </Button>
                      )}
                      {["draft", "released", "in_progress"].includes(o.status) && (
                        <Button variant="ghost" onClick={() => run(o.id, "cancel")}>Cancel</Button>
                      )}
                    </div>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
    </div>
  );
}
