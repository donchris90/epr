import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input } from "../../components/ui";
import { useTanks, useCreateIssue, useCountersignIssue, useTheftFlags, useEscalateUnresolvedTheftFlags } from "./hooks";

export default function IssuesPage() {
  const { data: tanks } = useTanks();
  const createIssue = useCreateIssue();
  const countersign = useCountersignIssue();
  const { data: theftFlags, isLoading } = useTheftFlags();
  const escalate = useEscalateUnresolvedTheftFlags();

  const [form, setForm] = useState({ tank_id: "", equipment_id: "", quantity_litres: "", issued_at: "" });
  const [lastIssue, setLastIssue] = useState<any>(null);

  async function handleIssue(e: React.FormEvent) {
    e.preventDefault();
    const res = await createIssue.mutateAsync(form);
    setLastIssue(res.data);
    setForm({ tank_id: "", equipment_id: "", quantity_litres: "", issued_at: "" });
  }

  return (
    <div>
      <PageHeader
        eyebrow="Fuel Management"
        title="Fuel Issues"
        action={
          <Button variant="secondary" onClick={() => escalate.mutate()} disabled={escalate.isPending}>
            {escalate.isPending ? "Checking…" : "Escalate unresolved theft flags"}
          </Button>
        }
      />

      <Card style={{ marginBottom: 20 }}>
        <h3 style={{ fontSize: 14, marginBottom: 4 }}>Issue fuel to equipment</h3>
        <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
          Issues above the countersignature threshold require a second sign-off before the record is considered
          complete.
        </p>
        <form onSubmit={handleIssue} style={{ display: "grid", gridTemplateColumns: "1.5fr 1.5fr 1fr 1fr auto", gap: 8 }}>
          <select
            required
            value={form.tank_id}
            onChange={(e) => setForm({ ...form, tank_id: e.target.value })}
            style={{ padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, background: "#fff" }}
          >
            <option value="">Tank…</option>
            {(tanks ?? []).map((t: any) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
          <Input required placeholder="Equipment ID" value={form.equipment_id} onChange={(e) => setForm({ ...form, equipment_id: e.target.value })} />
          <Input required placeholder="Litres" value={form.quantity_litres} onChange={(e) => setForm({ ...form, quantity_litres: e.target.value })} />
          <Input required type="datetime-local" value={form.issued_at} onChange={(e) => setForm({ ...form, issued_at: e.target.value })} />
          <Button type="submit" disabled={createIssue.isPending}>Issue</Button>
        </form>

        {lastIssue && (
          <div style={{ marginTop: 12, padding: "10px 12px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13 }}>
            {lastIssue.requires_countersignature ? (
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span>
                  <Badge tone="amber">Requires countersignature</Badge> — {lastIssue.quantity_litres} L over the threshold
                </span>
                <Button variant="secondary" disabled={countersign.isPending} onClick={() => countersign.mutate(lastIssue.id)}>
                  Countersign now
                </Button>
              </div>
            ) : (
              <Badge tone="green">Issued — no countersignature required</Badge>
            )}
          </div>
        )}
      </Card>

      <Card>
        <h3 style={{ fontSize: 14, marginBottom: 12 }}>Theft flags</h3>
        {isLoading ? (
          <p>Loading…</p>
        ) : !theftFlags?.length ? (
          <EmptyState title="No theft flags" hint="A reconciliation variance beyond tolerance raises a flag here automatically." />
        ) : (
          <Table>
            <thead><tr><Th>Tank</Th><Th>Status</Th></tr></thead>
            <tbody>
              {theftFlags.map((f: any) => (
                <tr key={f.id}>
                  <Td mono style={{ fontSize: 11 }}>{(f.tank_id || "").slice(0, 8)}…</Td>
                  <Td><Badge tone={f.status === "resolved" ? "green" : "brick"}>{f.status}</Badge></Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}
