import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, Input, ErrorBanner, EmptyState } from "../../components/ui";
import { WarehouseSelect } from "../../components/WarehouseSelect";
import { MaterialItemSelect } from "../../components/MaterialItemSelect";
import { getErrorMessage } from "../../api/client";
import {
  useReceiveStock,
  useIssueStock,
  useReorderLevelsBelowThreshold,
  useExpiringBatches,
} from "./hooks";

export default function StockMovementsPage() {
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

      <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 20 }}>
        <Card>
          <h3 style={{ fontSize: 14, marginBottom: 12 }}>Receive stock</h3>
          <form onSubmit={handleReceive}>
            <WarehouseAndItemSelect form={receiveForm} setForm={setReceiveForm} />
            <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 8 }}>
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
            <WarehouseAndItemSelect form={issueForm} setForm={setIssueForm} />
            <div style={{ marginTop: 8 }}>
              <Input required placeholder="Quantity" value={issueForm.quantity} onChange={(e) => setIssueForm({ ...issueForm, quantity: e.target.value })} />
            </div>
            <Button type="submit" disabled={issueStock.isPending} style={{ marginTop: 12 }}>
              {issueStock.isPending ? "Recording…" : "Issue"}
            </Button>
          </form>
        </Card>
      </div>

      <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
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
            <EmptyState compact title="Nothing below its reorder point right now." />
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
            <EmptyState compact title="No batches nearing expiry." />
          )}
        </Card>
      </div>
    </div>
  );
}

function WarehouseAndItemSelect<T extends { warehouse_id: string; material_item_id: string }>({
  form,
  setForm,
}: {
  form: T;
  setForm: (form: T) => void;
}) {
  return (
    <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
      <WarehouseSelect required value={form.warehouse_id} onChange={(warehouse_id) => setForm({ ...form, warehouse_id })} />
      <MaterialItemSelect required value={form.material_item_id} onChange={(material_item_id) => setForm({ ...form, material_item_id })} />
    </div>
  );
}
