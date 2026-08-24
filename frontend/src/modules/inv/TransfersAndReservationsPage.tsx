import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, ErrorBanner, Field, Input } from "../../components/ui";
import { WarehouseSelect } from "../../components/WarehouseSelect";
import { MaterialItemSelect } from "../../components/MaterialItemSelect";
import { getErrorMessage } from "../../api/client";
import {
  useStockTransfers,
  useCreateTransfer,
  useConfirmTransferReceipt,
  useReservations,
  useCreateReservation,
  useReleaseReservation,
} from "./hooks";

function statusTone(status: string): "green" | "neutral" | "brick" | "amber" {
  if (status === "confirmed" || status === "active") return "green";
  if (status === "cancelled" || status === "released") return "neutral";
  return "amber";
}

/** Real stock transfers and reservations, backed by the real
 * GET/POST endpoints added while closing this batch's own
 * frontend-backend gap audit (previously only POST existed, no way
 * to ever list a transfer or reservation again). */
export default function TransfersAndReservationsPage() {
  return (
    <div>
      <PageHeader eyebrow="Inventory" title="Transfers & Reservations" />
      <div style={{ display: "grid", gap: 24 }}>
        <TransfersSection />
        <ReservationsSection />
      </div>
    </div>
  );
}

function TransfersSection() {
  const { data: transfers } = useStockTransfers();
  const createTransfer = useCreateTransfer();
  const confirmReceipt = useConfirmTransferReceipt();
  const [form, setForm] = useState({ from_warehouse_id: "", to_warehouse_id: "", material_item_id: "", quantity: "" });
  const [error, setError] = useState<string | null>(null);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createTransfer.mutateAsync(form);
      setForm({ from_warehouse_id: "", to_warehouse_id: "", material_item_id: "", quantity: "" });
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <div>
      <h3 style={{ fontSize: 14, marginBottom: 12 }}>Stock transfers</h3>
      <Card style={{ marginBottom: 16 }}>
        <form onSubmit={handleCreate} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr auto", gap: 8 }}>
          <Field label="From"><WarehouseSelect required value={form.from_warehouse_id} onChange={(v) => setForm({ ...form, from_warehouse_id: v })} /></Field>
          <Field label="To"><WarehouseSelect required value={form.to_warehouse_id} onChange={(v) => setForm({ ...form, to_warehouse_id: v })} /></Field>
          <Field label="Material"><MaterialItemSelect required value={form.material_item_id} onChange={(v) => setForm({ ...form, material_item_id: v })} /></Field>
          <Field label="Quantity">
            <Input required type="number" step="0.01" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
          </Field>
          <Button type="submit" disabled={createTransfer.isPending} style={{ height: 38, alignSelf: "end" }}>
            {createTransfer.isPending ? "Sending…" : "Transfer"}
          </Button>
        </form>
        {error && <div style={{ marginTop: 12 }}><ErrorBanner title="Could not create transfer" detail={error} onDismiss={() => setError(null)} /></div>}
      </Card>
      <Card style={{ padding: 0 }}>
        {!transfers?.length ? (
          <EmptyState compact title="No stock transfers yet." />
        ) : (
          <Table>
            <thead><tr><Th>Quantity</Th><Th>Status</Th><Th /></tr></thead>
            <tbody>
              {transfers.map((t) => (
                <tr key={t.id}>
                  <Td mono>{t.quantity}</Td>
                  <Td><Badge tone={statusTone(t.status)}>{t.status}</Badge></Td>
                  <Td style={{ textAlign: "right" }}>
                    {t.status === "in_transit" && (
                      <button
                        onClick={() => confirmReceipt.mutate(t.id)}
                        disabled={confirmReceipt.isPending}
                        style={{ background: "none", border: "none", color: "var(--sf-green)", fontWeight: 600, cursor: "pointer" }}
                      >
                        Confirm receipt
                      </button>
                    )}
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

function ReservationsSection() {
  const { data: reservations } = useReservations();
  const createReservation = useCreateReservation();
  const releaseReservation = useReleaseReservation();
  const [form, setForm] = useState({ warehouse_id: "", material_item_id: "", quantity: "" });
  const [error, setError] = useState<string | null>(null);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createReservation.mutateAsync(form);
      setForm({ warehouse_id: "", material_item_id: "", quantity: "" });
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <div>
      <h3 style={{ fontSize: 14, marginBottom: 12 }}>Stock reservations</h3>
      <Card style={{ marginBottom: 16 }}>
        <form onSubmit={handleCreate} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr auto", gap: 8 }}>
          <Field label="Warehouse"><WarehouseSelect required value={form.warehouse_id} onChange={(v) => setForm({ ...form, warehouse_id: v })} /></Field>
          <Field label="Material"><MaterialItemSelect required value={form.material_item_id} onChange={(v) => setForm({ ...form, material_item_id: v })} /></Field>
          <Field label="Quantity">
            <Input required type="number" step="0.01" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
          </Field>
          <Button type="submit" disabled={createReservation.isPending} style={{ height: 38, alignSelf: "end" }}>
            {createReservation.isPending ? "Reserving…" : "Reserve"}
          </Button>
        </form>
        {error && <div style={{ marginTop: 12 }}><ErrorBanner title="Could not create reservation" detail={error} onDismiss={() => setError(null)} /></div>}
      </Card>
      <Card style={{ padding: 0 }}>
        {!reservations?.length ? (
          <EmptyState compact title="No stock reservations yet." />
        ) : (
          <Table>
            <thead><tr><Th>Quantity</Th><Th>Status</Th><Th /></tr></thead>
            <tbody>
              {reservations.map((r) => (
                <tr key={r.id}>
                  <Td mono>{r.quantity}</Td>
                  <Td><Badge tone={statusTone(r.status)}>{r.status}</Badge></Td>
                  <Td style={{ textAlign: "right" }}>
                    {r.status === "active" && (
                      <button
                        onClick={() => releaseReservation.mutate(r.id)}
                        disabled={releaseReservation.isPending}
                        style={{ background: "none", border: "none", color: "var(--sf-steel)", cursor: "pointer" }}
                      >
                        Release
                      </button>
                    )}
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
