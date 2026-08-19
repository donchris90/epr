import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, EmptyState, Input, Field, Select, Badge, formatMoney } from "../../components/ui";
import { useClients } from "./hooks";
import { useLeads, useCreateLead, useConvertLead } from "./hooks";

export default function LeadsPage() {
  const { data: leads, isLoading } = useLeads();
  const { data: clients } = useClients();
  const createLead = useCreateLead();
  const convertLead = useConvertLead();

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [source, setSource] = useState("");
  const [convertingLeadId, setConvertingLeadId] = useState<string | null>(null);
  const [convertClientId, setConvertClientId] = useState("");

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    await createLead.mutateAsync({ name, source: source || undefined });
    setName("");
    setSource("");
    setShowForm(false);
  }

  async function handleConvert(leadId: string) {
    if (!convertClientId) return;
    await convertLead.mutateAsync({ leadId, clientId: convertClientId });
    setConvertingLeadId(null);
    setConvertClientId("");
  }

  return (
    <div>
      <PageHeader
        eyebrow="Business Development"
        title="Leads"
        action={<Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "New lead"}</Button>}
      />

      {showForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreate}>
            <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <Field label="Lead name">
                <Input required value={name} onChange={(e) => setName(e.target.value)} placeholder="New Highway Extension" />
              </Field>
              <Field label="Source (optional)">
                <Input value={source} onChange={(e) => setSource(e.target.value)} placeholder="Referral, tender board, etc." />
              </Field>
            </div>
            <Button type="submit" disabled={createLead.isPending}>
              {createLead.isPending ? "Saving…" : "Save lead"}
            </Button>
          </form>
        </Card>
      )}

      {isLoading ? (
        <p>Loading…</p>
      ) : !leads?.length ? (
        <EmptyState title="No leads yet" hint="Log a lead as soon as you hear about a potential opportunity." />
      ) : (
        <Card style={{ padding: 0 }}>
          <Table>
            <thead>
              <tr>
                <Th>Name</Th>
                <Th>Source</Th>
                <Th>Est. value</Th>
                <Th>Status</Th>
                <Th></Th>
              </tr>
            </thead>
            <tbody>
              {leads.map((l) => (
                <tr key={l.id}>
                  <Td>{l.name}</Td>
                  <Td>{l.source || "—"}</Td>
                  <Td mono>{formatMoney(l.estimated_value)}</Td>
                  <Td>
                    <Badge tone={l.status === "open" ? "steel" : "neutral"}>{l.status}</Badge>
                  </Td>
                  <Td>
                    {l.status === "open" &&
                      (convertingLeadId === l.id ? (
                        <div style={{ display: "flex", gap: 6 }}>
                          <Select value={convertClientId} onChange={(e) => setConvertClientId(e.target.value)}>
                            <option value="">Select client…</option>
                            {clients?.map((c) => (
                              <option key={c.id} value={c.id}>
                                {c.name}
                              </option>
                            ))}
                          </Select>
                          <Button variant="secondary" onClick={() => handleConvert(l.id)} disabled={!convertClientId}>
                            Go
                          </Button>
                        </div>
                      ) : (
                        <Button variant="ghost" onClick={() => setConvertingLeadId(l.id)}>
                          Convert to opportunity →
                        </Button>
                      ))}
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
