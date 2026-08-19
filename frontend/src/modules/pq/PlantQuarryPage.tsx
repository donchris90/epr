import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input } from "../../components/ui";
import {
  useStockpiles,
  useCreateStockpile,
  useReconcileStockpile,
  useExplosivesRegister,
  useCreateExplosivesEntry,
  useAddExplosivesCorrection,
  useExplosivesBalance,
} from "./hooks";

export default function PlantQuarryPage() {
  const { data: stockpiles, isLoading } = useStockpiles();
  const createStockpile = useCreateStockpile();
  const reconcileStockpile = useReconcileStockpile();
  const [stockpileForm, setStockpileForm] = useState({ material_type: "", quantity: "" });
  const [reconcileId, setReconcileId] = useState<string | null>(null);
  const [physicalQty, setPhysicalQty] = useState("");

  const { data: explosivesEntries } = useExplosivesRegister();
  const createEntry = useCreateExplosivesEntry();
  const addCorrection = useAddExplosivesCorrection();
  const { data: balance } = useExplosivesBalance();
  const [entryForm, setEntryForm] = useState({ entry_type: "procurement", material_type: "", quantity: "" });
  const [correctionReason, setCorrectionReason] = useState<Record<string, string>>({});

  async function handleCreateStockpile(e: React.FormEvent) {
    e.preventDefault();
    await createStockpile.mutateAsync(stockpileForm);
    setStockpileForm({ material_type: "", quantity: "" });
  }

  async function handleReconcile(e: React.FormEvent) {
    e.preventDefault();
    if (!reconcileId) return;
    await reconcileStockpile.mutateAsync({ stockpileId: reconcileId, physical_quantity: physicalQty });
    setPhysicalQty("");
    setReconcileId(null);
  }

  async function handleCreateEntry(e: React.FormEvent) {
    e.preventDefault();
    await createEntry.mutateAsync(entryForm);
    setEntryForm({ entry_type: "procurement", material_type: "", quantity: "" });
  }

  return (
    <div>
      <PageHeader eyebrow="Plant & Quarry Management" title="Stockpiles & Explosives Register" />

      <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        <Card>
          <h3 style={{ fontSize: 14, marginBottom: 12 }}>Stockpiles</h3>
          <form onSubmit={handleCreateStockpile} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr auto", gap: 8, marginBottom: 12 }}>
            <Input required placeholder="Material type" value={stockpileForm.material_type} onChange={(e) => setStockpileForm({ ...stockpileForm, material_type: e.target.value })} />
            <Input placeholder="Initial qty" value={stockpileForm.quantity} onChange={(e) => setStockpileForm({ ...stockpileForm, quantity: e.target.value })} />
            <Button type="submit" disabled={createStockpile.isPending}>Add</Button>
          </form>

          {isLoading ? (
            <p>Loading…</p>
          ) : !stockpiles?.length ? (
            <EmptyState title="No stockpiles yet" hint="Register a stockpile to start tracking production and reconciliation." />
          ) : (
            <Table>
              <thead><tr><Th>Material</Th><Th>Quantity</Th><Th></Th></tr></thead>
              <tbody>
                {stockpiles.map((s: any) => (
                  <tr key={s.id}>
                    <Td>{s.material_type}</Td>
                    <Td mono>{s.quantity}</Td>
                    <Td>
                      {reconcileId === s.id ? (
                        <form onSubmit={handleReconcile} style={{ display: "flex", gap: 6 }}>
                          <Input placeholder="Physical qty" value={physicalQty} onChange={(e) => setPhysicalQty(e.target.value)} style={{ width: 100, fontSize: 11 }} />
                          <Button type="submit" disabled={reconcileStockpile.isPending}>Go</Button>
                        </form>
                      ) : (
                        <button onClick={() => setReconcileId(s.id)} style={{ background: "none", border: "none", color: "var(--sf-steel)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
                          Reconcile
                        </button>
                      )}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>

        <Card>
          <h3 style={{ fontSize: 14, marginBottom: 4 }}>Explosives register</h3>
          <p style={{ fontSize: 11, color: "var(--sf-navy-400)", marginBottom: 12 }}>
            Append-only — a mistake is corrected with a new row, never an edit to the original.
          </p>
          {balance && (
            <div style={{ marginBottom: 12, fontSize: 13 }}>
              Current balance: <span className="sf-mono" style={{ fontWeight: 700 }}>{balance.balance ?? "—"}</span>
            </div>
          )}
          <form onSubmit={handleCreateEntry} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1.5fr 1fr auto", gap: 8, marginBottom: 12 }}>
            <select
              value={entryForm.entry_type}
              onChange={(e) => setEntryForm({ ...entryForm, entry_type: e.target.value })}
              style={{ padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, background: "#fff" }}
            >
              <option value="procurement">Procurement</option>
              <option value="storage">Storage</option>
              <option value="issuance">Issuance</option>
              <option value="consumption">Consumption</option>
            </select>
            <Input required placeholder="Material type" value={entryForm.material_type} onChange={(e) => setEntryForm({ ...entryForm, material_type: e.target.value })} />
            <Input required placeholder="Quantity" value={entryForm.quantity} onChange={(e) => setEntryForm({ ...entryForm, quantity: e.target.value })} />
            <Button type="submit" disabled={createEntry.isPending}>Add</Button>
          </form>

          {explosivesEntries?.length ? (
            <Table>
              <thead><tr><Th>Type</Th><Th>Qty</Th><Th></Th></tr></thead>
              <tbody>
                {explosivesEntries.map((e: any) => (
                  <tr key={e.id}>
                    <Td><Badge tone="neutral">{e.entry_type}</Badge></Td>
                    <Td mono>{e.quantity}</Td>
                    <Td>
                      <div style={{ display: "flex", gap: 6 }}>
                        <Input
                          placeholder="Correction reason"
                          value={correctionReason[e.id] || ""}
                          onChange={(ev) => setCorrectionReason({ ...correctionReason, [e.id]: ev.target.value })}
                          style={{ width: 110, fontSize: 11 }}
                        />
                        <button
                          disabled={!correctionReason[e.id]}
                          onClick={() => addCorrection.mutate({ entryId: e.id, reason: correctionReason[e.id] })}
                          style={{ background: "none", border: "none", color: "var(--sf-steel)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}
                        >
                          Correct
                        </button>
                      </div>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <p style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>No entries yet.</p>
          )}
        </Card>
      </div>
    </div>
  );
}
