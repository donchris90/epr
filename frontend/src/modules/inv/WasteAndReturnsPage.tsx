import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, ErrorBanner, Field, Input, Select, formatMoney } from "../../components/ui";
import { WarehouseSelect } from "../../components/WarehouseSelect";
import { MaterialItemSelect } from "../../components/MaterialItemSelect";
import { getErrorMessage } from "../../api/client";
import { useWasteRecords, useRecordWaste, useMaterialReturns, useReturnToYard } from "./hooks";

const WASTE_CAUSES = ["breakage", "theft", "spoilage", "over_order"];

/** Real waste tracking and material returns (to-yard), backed by the
 * real GET/POST endpoints added while closing this batch's own
 * frontend-backend gap audit. Return-to-vendor is deliberately not
 * built here yet -- it needs a real VendorSelect wired to a real
 * credit-note-reference flow, a slightly larger scope than this
 * pass; return-to-yard (the far more common, internal case) is
 * complete. */
export default function WasteAndReturnsPage() {
  return (
    <div>
      <PageHeader eyebrow="Inventory" title="Waste & Returns" />
      <div style={{ display: "grid", gap: 24 }}>
        <WasteSection />
        <ReturnsSection />
      </div>
    </div>
  );
}

function WasteSection() {
  const { data: records } = useWasteRecords();
  const recordWaste = useRecordWaste();
  const [form, setForm] = useState({ warehouse_id: "", material_item_id: "", quantity: "", cause_classification: "breakage" });
  const [error, setError] = useState<string | null>(null);

  async function handleRecord(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await recordWaste.mutateAsync(form);
      setForm({ warehouse_id: "", material_item_id: "", quantity: "", cause_classification: "breakage" });
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <div>
      <h3 style={{ fontSize: 14, marginBottom: 12 }}>Waste records</h3>
      <Card style={{ marginBottom: 16 }}>
        <form onSubmit={handleRecord} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr auto", gap: 8 }}>
          <Field label="Warehouse"><WarehouseSelect required value={form.warehouse_id} onChange={(v) => setForm({ ...form, warehouse_id: v })} /></Field>
          <Field label="Material"><MaterialItemSelect required value={form.material_item_id} onChange={(v) => setForm({ ...form, material_item_id: v })} /></Field>
          <Field label="Quantity"><Input required type="number" step="0.01" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} /></Field>
          <Field label="Cause">
            <Select value={form.cause_classification} onChange={(e) => setForm({ ...form, cause_classification: e.target.value })}>
              {WASTE_CAUSES.map((c) => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}
            </Select>
          </Field>
          <Button type="submit" disabled={recordWaste.isPending} style={{ height: 38, alignSelf: "end" }}>
            {recordWaste.isPending ? "Recording…" : "Record"}
          </Button>
        </form>
        {error && <div style={{ marginTop: 12 }}><ErrorBanner title="Could not record waste" detail={error} onDismiss={() => setError(null)} /></div>}
      </Card>
      <Card style={{ padding: 0 }}>
        {!records?.length ? (
          <EmptyState compact title="No waste recorded yet." />
        ) : (
          <Table>
            <thead><tr><Th>Quantity</Th><Th>Cause</Th><Th>Valued cost</Th></tr></thead>
            <tbody>
              {records.map((r) => (
                <tr key={r.id}>
                  <Td mono>{r.quantity}</Td>
                  <Td>{r.cause_classification.replace(/_/g, " ")}</Td>
                  <Td mono>{formatMoney(r.valued_cost)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}

function ReturnsSection() {
  const { data: returns } = useMaterialReturns();
  const returnToYard = useReturnToYard();
  const [form, setForm] = useState({ material_item_id: "", source_warehouse_id: "", destination_warehouse_id: "", quantity: "" });
  const [error, setError] = useState<string | null>(null);

  async function handleReturn(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await returnToYard.mutateAsync(form);
      setForm({ material_item_id: "", source_warehouse_id: "", destination_warehouse_id: "", quantity: "" });
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <div>
      <h3 style={{ fontSize: 14, marginBottom: 12 }}>Material returns to yard</h3>
      <Card style={{ marginBottom: 16 }}>
        <form onSubmit={handleReturn} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr auto", gap: 8 }}>
          <Field label="Material"><MaterialItemSelect required value={form.material_item_id} onChange={(v) => setForm({ ...form, material_item_id: v })} /></Field>
          <Field label="From (source)"><WarehouseSelect required value={form.source_warehouse_id} onChange={(v) => setForm({ ...form, source_warehouse_id: v })} /></Field>
          <Field label="To (yard)"><WarehouseSelect required value={form.destination_warehouse_id} onChange={(v) => setForm({ ...form, destination_warehouse_id: v })} /></Field>
          <Field label="Quantity"><Input required type="number" step="0.01" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} /></Field>
          <Button type="submit" disabled={returnToYard.isPending} style={{ height: 38, alignSelf: "end" }}>
            {returnToYard.isPending ? "Returning…" : "Return"}
          </Button>
        </form>
        {error && <div style={{ marginTop: 12 }}><ErrorBanner title="Could not process return" detail={error} onDismiss={() => setError(null)} /></div>}
      </Card>
      <Card style={{ padding: 0 }}>
        {!returns?.length ? (
          <EmptyState compact title="No material returns yet." />
        ) : (
          <Table>
            <thead><tr><Th>Quantity</Th><Th>Type</Th><Th>Status</Th></tr></thead>
            <tbody>
              {returns.map((r) => (
                <tr key={r.id}>
                  <Td mono>{r.quantity}</Td>
                  <Td>{r.return_type === "site_to_yard" ? "To yard" : "To vendor"}</Td>
                  <Td><Badge tone="neutral">{r.status}</Badge></Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}
