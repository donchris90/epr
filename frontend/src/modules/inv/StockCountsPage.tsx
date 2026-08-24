import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, ErrorBanner, Field, Input, Select } from "../../components/ui";
import { WarehouseSelect } from "../../components/WarehouseSelect";
import { MaterialItemSelect } from "../../components/MaterialItemSelect";
import { getErrorMessage } from "../../api/client";
import {
  useStockCounts,
  useStockCount,
  useStartStockCount,
  useRecordCountLine,
  useCompleteStockCount,
  useApplyStockCountAdjustment,
} from "./hooks";

const COUNT_TYPES = ["cycle", "full"];

function statusTone(status: string): "green" | "neutral" | "brick" | "amber" {
  if (status === "adjusted") return "green";
  if (status === "completed") return "amber";
  return "neutral";
}

/** Real stock counts (start -> record each line -> complete -> apply
 * adjustment), backed by the real GET list/detail endpoints added
 * while closing this batch's own frontend-backend gap audit --
 * previously there was no way to ever see a count's own lines at
 * all, making a real recording UI impossible to build honestly. */
export default function StockCountsPage() {
  const [selectedCountId, setSelectedCountId] = useState<string | null>(null);

  if (selectedCountId) {
    return <StockCountDetail countId={selectedCountId} onBack={() => setSelectedCountId(null)} />;
  }

  return <StockCountsList onSelect={setSelectedCountId} />;
}

function StockCountsList({ onSelect }: { onSelect: (id: string) => void }) {
  const { data: counts } = useStockCounts();
  const startCount = useStartStockCount();
  const [form, setForm] = useState({ warehouse_id: "", count_type: "cycle" });
  const [selectedItems, setSelectedItems] = useState<string[]>([]);
  const [itemToAdd, setItemToAdd] = useState("");
  const [error, setError] = useState<string | null>(null);

  function addItem() {
    if (itemToAdd && !selectedItems.includes(itemToAdd)) {
      setSelectedItems([...selectedItems, itemToAdd]);
      setItemToAdd("");
    }
  }

  async function handleStart(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await startCount.mutateAsync({ ...form, material_item_ids: selectedItems });
      setForm({ warehouse_id: "", count_type: "cycle" });
      setSelectedItems([]);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <div>
      <PageHeader eyebrow="Inventory" title="Stock Counts" />
      <Card style={{ marginBottom: 16 }}>
        <h3 style={{ fontSize: 14, marginBottom: 12 }}>Start a stock count</h3>
        <form onSubmit={handleStart}>
          <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
            <Field label="Warehouse"><WarehouseSelect required value={form.warehouse_id} onChange={(v) => setForm({ ...form, warehouse_id: v })} /></Field>
            <Field label="Count type">
              <Select value={form.count_type} onChange={(e) => setForm({ ...form, count_type: e.target.value })}>
                {COUNT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </Select>
            </Field>
          </div>
          <Field label="Items to count">
            <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
              <MaterialItemSelect value={itemToAdd} onChange={setItemToAdd} />
              <Button type="button" variant="secondary" onClick={addItem} disabled={!itemToAdd}>Add</Button>
            </div>
            {selectedItems.length > 0 && (
              <div style={{ fontSize: 12, color: "var(--sf-navy-600)" }}>{selectedItems.length} item(s) selected</div>
            )}
          </Field>
          {error && <div style={{ marginTop: 8 }}><ErrorBanner title="Could not start count" detail={error} onDismiss={() => setError(null)} /></div>}
          <Button type="submit" disabled={startCount.isPending || !selectedItems.length} style={{ marginTop: 12 }}>
            {startCount.isPending ? "Starting…" : "Start count"}
          </Button>
        </form>
      </Card>

      <Card style={{ padding: 0 }}>
        {!counts?.length ? (
          <EmptyState compact title="No stock counts yet." />
        ) : (
          <Table>
            <thead><tr><Th>Type</Th><Th>Lines</Th><Th>Status</Th><Th /></tr></thead>
            <tbody>
              {counts.map((c) => (
                <tr key={c.id}>
                  <Td>{c.count_type}</Td>
                  <Td mono>{c.lines?.length ?? 0}</Td>
                  <Td><Badge tone={statusTone(c.status)}>{c.status}</Badge></Td>
                  <Td style={{ textAlign: "right" }}>
                    <button onClick={() => onSelect(c.id)} style={{ background: "none", border: "none", color: "var(--sf-steel)", cursor: "pointer", fontWeight: 600 }}>
                      Open →
                    </button>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}

function StockCountDetail({ countId, onBack }: { countId: string; onBack: () => void }) {
  const { data: count, isLoading, error: loadError } = useStockCount(countId);
  const recordLine = useRecordCountLine(countId);
  const completeCount = useCompleteStockCount();
  const applyAdjustment = useApplyStockCountAdjustment();
  const [lineInputs, setLineInputs] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  async function handleSaveLine(lineId: string) {
    setError(null);
    try {
      await recordLine.mutateAsync({ lineId, counted_quantity: lineInputs[lineId] });
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  async function handleComplete() {
    setError(null);
    try {
      await completeCount.mutateAsync(countId);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  async function handleApplyAdjustment() {
    if (!confirm("Apply this stock count's adjustments to real inventory levels? This cannot be undone.")) return;
    setError(null);
    try {
      await applyAdjustment.mutateAsync(countId);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  if (isLoading) return <div style={{ padding: 32, fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>;
  if (loadError || !count) return <ErrorBanner title="Could not load stock count" detail={getErrorMessage(loadError)} />;

  return (
    <div>
      <PageHeader
        eyebrow="Inventory"
        title={`${count.count_type} count`}
        action={<Badge tone={statusTone(count.status)}>{count.status}</Badge>}
      />
      <button onClick={onBack} style={{ background: "none", border: "none", color: "var(--sf-steel)", cursor: "pointer", fontSize: 12, marginBottom: 16 }}>
        ← Back to counts
      </button>

      {error && <div style={{ marginBottom: 16 }}><ErrorBanner title="Action failed" detail={error} onDismiss={() => setError(null)} /></div>}

      <Card style={{ padding: 0, marginBottom: 16 }}>
        <Table>
          <thead><tr><Th>System qty</Th><Th>Counted qty</Th><Th>Variance</Th><Th /></tr></thead>
          <tbody>
            {count.lines.map((line) => (
              <tr key={line.id}>
                <Td mono>{line.system_quantity}</Td>
                <Td mono>{line.counted_quantity ?? "—"}</Td>
                <Td mono>{line.variance ?? "—"}</Td>
                <Td style={{ display: "flex", gap: 8, alignItems: "center", justifyContent: "flex-end" }}>
                  {count.status === "in_progress" && (
                    <>
                      <Input
                        type="number"
                        step="0.01"
                        placeholder="Counted qty"
                        value={lineInputs[line.id] ?? ""}
                        onChange={(e) => setLineInputs({ ...lineInputs, [line.id]: e.target.value })}
                        style={{ width: 120 }}
                      />
                      <Button
                        variant="secondary"
                        onClick={() => handleSaveLine(line.id)}
                        disabled={!lineInputs[line.id] || recordLine.isPending}
                      >
                        Save
                      </Button>
                    </>
                  )}
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>

      {count.status === "in_progress" && (
        <Button onClick={handleComplete} disabled={completeCount.isPending}>
          {completeCount.isPending ? "Completing…" : "Complete count"}
        </Button>
      )}
      {count.status === "completed" && (
        <Button onClick={handleApplyAdjustment} disabled={applyAdjustment.isPending}>
          {applyAdjustment.isPending ? "Applying…" : "Apply adjustment to inventory"}
        </Button>
      )}
    </div>
  );
}
