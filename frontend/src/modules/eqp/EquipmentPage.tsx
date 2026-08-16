import { useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input, Field } from "../../components/ui";
import { useEquipmentList, useCreateEquipment, useIdleEquipment, useOverdueMaintenance } from "./hooks";

const STATUS_TONE: Record<string, "neutral" | "amber" | "steel" | "green" | "brick"> = {
  available: "green",
  in_use: "steel",
  under_maintenance: "amber",
  out_of_service: "brick",
};

export default function EquipmentPage() {
  const { data: equipment, isLoading } = useEquipmentList();
  const { data: idle } = useIdleEquipment();
  const { data: overdueMaintenance } = useOverdueMaintenance();
  const createEquipment = useCreateEquipment();

  const idleIds = new Set((idle ?? []).map((e: any) => e.id));

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", make: "", model: "", ownership_type: "owned" });

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    await createEquipment.mutateAsync(form);
    setForm({ name: "", make: "", model: "", ownership_type: "owned" });
    setShowForm(false);
  }

  return (
    <div>
      <PageHeader
        eyebrow="Equipment & Fleet"
        title="Equipment"
        action={<Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "New equipment"}</Button>}
      />

      {overdueMaintenance?.length ? (
        <Card style={{ marginBottom: 20, borderColor: "var(--sf-brick)" }}>
          <div style={{ fontSize: 13, color: "var(--sf-brick)", fontWeight: 600 }}>
            {overdueMaintenance.length} equipment item(s) have overdue maintenance
          </div>
        </Card>
      ) : null}

      {showForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreate} style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr auto", gap: 12 }}>
            <Field label="Name">
              <Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </Field>
            <Field label="Make">
              <Input value={form.make} onChange={(e) => setForm({ ...form, make: e.target.value })} />
            </Field>
            <Field label="Model">
              <Input value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} />
            </Field>
            <Field label="Ownership">
              <select
                value={form.ownership_type}
                onChange={(e) => setForm({ ...form, ownership_type: e.target.value })}
                style={{ padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, background: "#fff" }}
              >
                <option value="owned">Owned</option>
                <option value="rented">Rented</option>
              </select>
            </Field>
            <Button type="submit" disabled={createEquipment.isPending} style={{ height: 38, alignSelf: "end" }}>Add</Button>
          </form>
        </Card>
      )}

      {isLoading ? (
        <p>Loading…</p>
      ) : !equipment?.length ? (
        <EmptyState title="No equipment registered" hint="Register equipment to start tracking utilization and maintenance." />
      ) : (
        <Card style={{ padding: 0 }}>
          <Table>
            <thead>
              <tr><Th>Name</Th><Th>Make / Model</Th><Th>Ownership</Th><Th>Status</Th><Th></Th></tr>
            </thead>
            <tbody>
              {equipment.map((e: any) => (
                <tr key={e.id}>
                  <Td>{e.name}</Td>
                  <Td>{[e.make, e.model].filter(Boolean).join(" / ") || "—"}</Td>
                  <Td><Badge tone="neutral">{e.ownership_type}</Badge></Td>
                  <Td>
                    <Badge tone={STATUS_TONE[e.status] ?? "neutral"}>{e.status}</Badge>
                    {idleIds.has(e.id) && <Badge tone="amber">Idle</Badge>}
                  </Td>
                  <Td>
                    <Link to={`${e.id}`} style={{ fontSize: 12, fontWeight: 600 }}>Open →</Link>
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
