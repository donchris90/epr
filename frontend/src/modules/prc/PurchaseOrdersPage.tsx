import { useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input, Field } from "../../components/ui";
import { usePurchaseOrders, useCreatePurchaseOrder, useVendors } from "./hooks";
import type { Vendor } from "./types";

const STATUS_TONE: Record<string, "neutral" | "amber" | "steel" | "green" | "brick"> = {
  draft: "neutral",
  pending_approval: "amber",
  approved: "steel",
  issued: "green",
  rejected: "brick",
};

export default function PurchaseOrdersPage() {
  const { data: pos, isLoading } = usePurchaseOrders();
  const { data: vendors } = useVendors();
  const createPO = useCreatePurchaseOrder();

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ vendor_id: "", po_number: "", total_value: "" });

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    await createPO.mutateAsync({ vendor_id: form.vendor_id, po_number: form.po_number, total_value: form.total_value });
    setForm({ vendor_id: "", po_number: "", total_value: "" });
    setShowForm(false);
  }

  const vendorsById: Record<string, Vendor> = Object.fromEntries((vendors ?? []).map((v) => [v.id, v]));

  return (
    <div>
      <PageHeader
        eyebrow="Procurement"
        title="Purchase Orders"
        action={<Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "New PO"}</Button>}
      />

      {showForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreate}>
            <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: 16 }}>
              <Field label="Vendor">
                <select
                  required
                  value={form.vendor_id}
                  onChange={(e) => setForm({ ...form, vendor_id: e.target.value })}
                  style={{ padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, width: "100%", background: "#fff" }}
                >
                  <option value="">Select…</option>
                  {(vendors ?? []).map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="PO number">
                <Input required value={form.po_number} onChange={(e) => setForm({ ...form, po_number: e.target.value })} />
              </Field>
              <Field label="Total value">
                <Input required value={form.total_value} onChange={(e) => setForm({ ...form, total_value: e.target.value })} />
              </Field>
            </div>
            <Button type="submit" disabled={createPO.isPending}>
              {createPO.isPending ? "Saving…" : "Save purchase order"}
            </Button>
          </form>
        </Card>
      )}

      {isLoading ? (
        <p>Loading…</p>
      ) : !pos?.length ? (
        <EmptyState title="No purchase orders yet" hint="Create one directly, or from an approved purchase request." />
      ) : (
        <Card style={{ padding: 0 }}>
          <Table>
            <thead>
              <tr>
                <Th>PO number</Th>
                <Th>Vendor</Th>
                <Th>Total value</Th>
                <Th>Status</Th>
                <Th></Th>
              </tr>
            </thead>
            <tbody>
              {pos.map((po) => (
                <tr key={po.id}>
                  <Td mono>{po.po_number}</Td>
                  <Td>{vendorsById[po.vendor_id]?.name || po.vendor_id.slice(0, 8) + "…"}</Td>
                  <Td mono>
                    {po.currency} {po.total_value}
                  </Td>
                  <Td>
                    <Badge tone={STATUS_TONE[po.status] ?? "neutral"}>{po.status.replace(/_/g, " ")}</Badge>
                  </Td>
                  <Td>
                    <Link to={`orders/${po.id}`} style={{ fontSize: 12, fontWeight: 600 }}>
                      Open →
                    </Link>
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
