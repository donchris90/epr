import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, Input, ErrorBanner } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import {
  useWarehouses,
  useMaterialItems,
  useReceiveStock,
  useIssueStock,
  useReorderLevelsBelowThreshold,
  useExpiringBatches,
} from "./hooks";

export default function StockMovementsPage() {
  const { data: warehouses } = useWarehouses();
  const { data: materialItems } = useMaterialItems();
  const { data: belowThreshold } = useReorderLevelsBelowThreshold();
  const { data: expiringBatches } = useExpiringBatches();

  const receiveStock = useReceiveStock();
  const issueStock = useIssueStock();

  const [receiveForm, setReceiveForm] = useState({ warehouse_id: "", material_item_id: "", quantity: "", unit_cost: "" });
  const [issueForm, setIssueForm] = useState({ warehouse_id: "", material_item_id: "", quantity: "" });
  const [error, setError] = useState<string | null>(null);

  async function handleReceive(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await receiveStock.mutateAsync(receiveForm);
      setReceiveForm({ warehouse_id: "", material_item_id: "", quantity: "", unit_cost: "" });
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  async function handleIssue(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await issueStock.mutateAsync(issueForm);
      setIssueForm({ warehouse_id: "", material_item_id: "", quantity: "" });
    } catch (err) {
      // Business rule: issuing more than what's on hand is blocked --
      // the exact shortfall shows up here via the backend's detail.
      setError(getErrorMessage(err));
    }
  }

  return (
    <div>
      <PageHeader eyebrow="Inventory & Warehouse" title="Stock Movements" />

      {error && <ErrorBanner title="Could not complete this movement" detail={error} onDismiss={() => setError(null)} />}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 20 }}>
        <Card>
          <h3 style={{ fontSize: 14, marginBottom: 12 }}>Receive stock</h3>
          <form onSubmit={handleReceive}>
            <WarehouseAndItemSelect warehouses={warehouses ?? []} materialItems={materialItems ?? []} form={receiveForm} setForm={setReceiveForm} />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 8 }}>
              <Input required placeholder="Quantity" value={receiveForm.quantity} onChange={(e) => setReceiveForm({ ...receiveForm, quantity: e.target.value })} />
              <Input required placeholder="Unit cost" value={receiveForm.unit_cost} onChange={(e) => setReceiveForm({ ...receiveForm, unit_cost: e.target.value })} />
            </div>
            <Button type="submit" disabled={receiveStock.isPending} style={{ marginTop: 12 }}>
              {receiveStock.isPending ? "Recording…" : "Receive"}
            </Button>
          </form>
        </Card>

        <Card>
          <h3 style={{ fontSize: 14, marginBottom: 12 }}>Issue stock</h3>
          <form onSubmit={handleIssue}>
            <WarehouseAndItemSelect warehouses={warehouses ?? []} materialItems={materialItems ?? []} form={issueForm} setForm={setIssueForm} />
            <div style={{ marginTop: 8 }}>
              <Input required placeholder="Quantity" value={issueForm.quantity} onChange={(e) => setIssueForm({ ...issueForm, quantity: e.target.value })} />
            </div>
            <Button type="submit" disabled={issueStock.isPending} style={{ marginTop: 12 }}>
              {issueStock.isPending ? "Recording…" : "Issue"}
            </Button>
          </form>
        </Card>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        <Card>
          <h3 style={{ fontSize: 14, marginBottom: 12 }}>Below reorder threshold</h3>
          {belowThreshold?.length ? (
            <Table>
              <thead><tr><Th>Warehouse</Th><Th>Reorder point</Th></tr></thead>
              <tbody>
                {belowThreshold.map((r: any) => (
                  <tr key={r.id}>
                    <Td mono style={{ fontSize: 11 }}>{r.warehouse_id.slice(0, 8)}…</Td>
                    <Td><Badge tone="amber">{r.reorder_point}</Badge></Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <p style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>Nothing below its reorder point right now.</p>
          )}
        </Card>

        <Card>
          <h3 style={{ fontSize: 14, marginBottom: 12 }}>Batches expiring soon</h3>
          {expiringBatches?.length ? (
            <Table>
              <thead><tr><Th>Batch</Th><Th>Expiry</Th></tr></thead>
              <tbody>
                {expiringBatches.map((b: any) => (
                  <tr key={b.id}>
                    <Td mono>{b.batch_number}</Td>
                    <Td><Badge tone="brick">{b.expiry_date}</Badge></Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <p style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>No batches nearing expiry.</p>
          )}
        </Card>
      </div>
    </div>
  );
}

function WarehouseAndItemSelect({ warehouses, materialItems, form, setForm }: any) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
      <select
        required
        value={form.warehouse_id}
        onChange={(e) => setForm({ ...form, warehouse_id: e.target.value })}
        style={{ padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, background: "#fff" }}
      >
        <option value="">Warehouse…</option>
        {warehouses.map((w: any) => (
          <option key={w.id} value={w.id}>{w.name}</option>
        ))}
      </select>
      <select
        required
        value={form.material_item_id}
        onChange={(e) => setForm({ ...form, material_item_id: e.target.value })}
        style={{ padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, background: "#fff" }}
      >
        <option value="">Material item…</option>
        {materialItems.map((m: any) => (
          <option key={m.id} value={m.id}>{m.code} — {m.description}</option>
        ))}
      </select>
    </div>
  );
}
