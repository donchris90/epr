import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input, Field } from "../../components/ui";
import { useVariationOrders, useCreateVariationOrder, useDecideVariationOrder } from "./hooks";

const STATUS_TONE: Record<string, "neutral" | "amber" | "steel" | "green" | "brick"> = {
  pending: "amber",
  approved: "green",
  rejected: "brick",
};

export default function VariationOrdersPage() {
  const [statusFilter, setStatusFilter] = useState("");
  const { data: vos, isLoading } = useVariationOrders(statusFilter || undefined);
  const createVO = useCreateVariationOrder();
  const decideVO = useDecideVariationOrder();

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ contract_id: "", boq_item_id: "", description: "", varied_quantity: "", varied_rate: "" });

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    await createVO.mutateAsync({
      contract_id: form.contract_id,
      boq_item_id: form.boq_item_id || undefined,
      description: form.description,
      varied_quantity: form.varied_quantity || undefined,
      varied_rate: form.varied_rate || undefined,
    });
    setForm({ contract_id: "", boq_item_id: "", description: "", varied_quantity: "", varied_rate: "" });
    setShowForm(false);
  }

  return (
    <div>
      <PageHeader
        eyebrow="Client Billing"
        title="Variation Orders"
        action={<Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "New variation order"}</Button>}
      />

      <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 16, maxWidth: 640 }}>
        A variation order not yet approved can be tracked here as pending value, but a Progress Certificate line can
        never reference it as billable until it's approved — the certificate detail page enforces that directly.
      </p>

      <div style={{ marginBottom: 20, maxWidth: 280 }}>
        <Field label="Filter by status">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, width: "100%", background: "#fff" }}
          >
            <option value="">All statuses</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </select>
        </Field>
      </div>

      {showForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreate}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <Field label="Contract ID">
                <Input required value={form.contract_id} onChange={(e) => setForm({ ...form, contract_id: e.target.value })} />
              </Field>
              <Field label="BOQ item ID (optional — blank if a new item)">
                <Input value={form.boq_item_id} onChange={(e) => setForm({ ...form, boq_item_id: e.target.value })} />
              </Field>
              <Field label="Varied quantity">
                <Input value={form.varied_quantity} onChange={(e) => setForm({ ...form, varied_quantity: e.target.value })} />
              </Field>
              <Field label="Varied rate">
                <Input value={form.varied_rate} onChange={(e) => setForm({ ...form, varied_rate: e.target.value })} />
              </Field>
            </div>
            <Field label="Description">
              <Input required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </Field>
            <Button type="submit" disabled={createVO.isPending}>
              {createVO.isPending ? "Saving…" : "Save variation order"}
            </Button>
          </form>
        </Card>
      )}

      {isLoading ? (
        <p>Loading…</p>
      ) : !vos?.length ? (
        <EmptyState title="No variation orders yet" hint="Record a scope change here before it can be billed." />
      ) : (
        <Card style={{ padding: 0 }}>
          <Table>
            <thead>
              <tr>
                <Th>Quantity</Th>
                <Th>Status</Th>
                <Th></Th>
              </tr>
            </thead>
            <tbody>
              {vos.map((vo: any) => (
                <tr key={vo.id}>
                  <Td mono>{vo.varied_quantity ?? "—"}</Td>
                  <Td>
                    <Badge tone={STATUS_TONE[vo.status] ?? "neutral"}>{vo.status}</Badge>
                  </Td>
                  <Td>
                    {vo.status === "pending" && (
                      <div style={{ display: "flex", gap: 10 }}>
                        <button
                          onClick={() => decideVO.mutate({ voId: vo.id, decision: "approved" })}
                          style={{ background: "none", border: "none", color: "var(--sf-green)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => decideVO.mutate({ voId: vo.id, decision: "rejected" })}
                          style={{ background: "none", border: "none", color: "var(--sf-brick)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}
                        >
                          Reject
                        </button>
                      </div>
                    )}
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
