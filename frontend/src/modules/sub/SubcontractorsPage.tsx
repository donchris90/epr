import { useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input, Field } from "../../components/ui";
import { useSubcontractors, useCreateSubcontractor, useAgreements, useCreateAgreement } from "./hooks";

export default function SubcontractorsPage() {
  const { data: subcontractors, isLoading } = useSubcontractors();
  const createSubcontractor = useCreateSubcontractor();
  const { data: agreements } = useAgreements();
  const createAgreement = useCreateAgreement();

  const [showSubForm, setShowSubForm] = useState(false);
  const [subForm, setSubForm] = useState({ name: "", trade_specialty: "" });

  const [showAgForm, setShowAgForm] = useState(false);
  const [agForm, setAgForm] = useState({ subcontractor_id: "", agreement_number: "", value: "", retention_percentage: "5" });

  async function handleCreateSub(e: React.FormEvent) {
    e.preventDefault();
    await createSubcontractor.mutateAsync(subForm);
    setSubForm({ name: "", trade_specialty: "" });
    setShowSubForm(false);
  }

  async function handleCreateAgreement(e: React.FormEvent) {
    e.preventDefault();
    await createAgreement.mutateAsync(agForm);
    setAgForm({ subcontractor_id: "", agreement_number: "", value: "", retention_percentage: "5" });
    setShowAgForm(false);
  }

  return (
    <div>
      <PageHeader
        eyebrow="Subcontractor Management"
        title="Subcontractors & Agreements"
        action={
          <div style={{ display: "flex", gap: 8 }}>
            <Button variant="secondary" onClick={() => setShowAgForm((v) => !v)}>
              {showAgForm ? "Cancel" : "New agreement"}
            </Button>
            <Button onClick={() => setShowSubForm((v) => !v)}>{showSubForm ? "Cancel" : "New subcontractor"}</Button>
          </div>
        }
      />

      {showSubForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreateSub} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr auto", gap: 12 }}>
            <Field label="Name">
              <Input required value={subForm.name} onChange={(e) => setSubForm({ ...subForm, name: e.target.value })} />
            </Field>
            <Field label="Trade specialty">
              <Input value={subForm.trade_specialty} onChange={(e) => setSubForm({ ...subForm, trade_specialty: e.target.value })} />
            </Field>
            <Button type="submit" disabled={createSubcontractor.isPending} style={{ height: 38, alignSelf: "end" }}>Add</Button>
          </form>
        </Card>
      )}

      {showAgForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreateAgreement} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr 1fr 1fr auto", gap: 12 }}>
            <select
              required
              value={agForm.subcontractor_id}
              onChange={(e) => setAgForm({ ...agForm, subcontractor_id: e.target.value })}
              style={{ padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, background: "#fff" }}
            >
              <option value="">Subcontractor…</option>
              {(subcontractors ?? []).map((s: any) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
            <Input required placeholder="Agreement number" value={agForm.agreement_number} onChange={(e) => setAgForm({ ...agForm, agreement_number: e.target.value })} />
            <Input required placeholder="Value" value={agForm.value} onChange={(e) => setAgForm({ ...agForm, value: e.target.value })} />
            <Input placeholder="Retention %" value={agForm.retention_percentage} onChange={(e) => setAgForm({ ...agForm, retention_percentage: e.target.value })} />
            <Button type="submit" disabled={createAgreement.isPending} style={{ height: 38, alignSelf: "end" }}>Add</Button>
          </form>
        </Card>
      )}

      {isLoading ? (
        <p>Loading…</p>
      ) : !subcontractors?.length ? (
        <EmptyState title="No subcontractors yet" hint="Register one and set up an agreement to start tracking measured work." />
      ) : (
        <Card style={{ padding: 0, marginBottom: 20 }}>
          <Table>
            <thead><tr><Th>Name</Th><Th>Trade</Th><Th>Status</Th></tr></thead>
            <tbody>
              {subcontractors.map((s: any) => (
                <tr key={s.id}>
                  <Td>{s.name}</Td>
                  <Td>{s.trade_specialty || "—"}</Td>
                  <Td><Badge tone={s.status === "active" ? "green" : "neutral"}>{s.status}</Badge></Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}

      {agreements?.length ? (
        <Card style={{ padding: 0 }}>
          <Table>
            <thead><tr><Th>Number</Th><Th>Value</Th><Th>Retention</Th><Th>Status</Th><Th></Th></tr></thead>
            <tbody>
              {agreements.map((a: any) => (
                <tr key={a.id}>
                  <Td mono>{a.agreement_number}</Td>
                  <Td mono>{a.currency} {a.value}</Td>
                  <Td mono>{a.retention_percentage}%</Td>
                  <Td><Badge tone="neutral">{a.status}</Badge></Td>
                  <Td><Link to={`agreements/${a.id}`} style={{ fontSize: 12, fontWeight: 600 }}>Open →</Link></Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      ) : null}
    </div>
  );
}
