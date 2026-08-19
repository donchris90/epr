import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, EmptyState, Input, Field } from "../../components/ui";
import { useClients, useCreateClient } from "./hooks";

export default function ClientsPage() {
  const { data: clients, isLoading } = useClients();
  const createClient = useCreateClient();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    await createClient.mutateAsync({ name, billing_email: email || undefined });
    setName("");
    setEmail("");
    setShowForm(false);
  }

  return (
    <div>
      <PageHeader
        eyebrow="Business Development"
        title="Clients"
        action={<Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "New client"}</Button>}
      />

      {showForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreate}>
            <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <Field label="Client name">
                <Input required value={name} onChange={(e) => setName(e.target.value)} placeholder="Acme Construction Ltd" />
              </Field>
              <Field label="Billing email (optional)">
                <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="accounts@acme.com" />
              </Field>
            </div>
            <Button type="submit" disabled={createClient.isPending}>
              {createClient.isPending ? "Saving…" : "Save client"}
            </Button>
          </form>
        </Card>
      )}

      {isLoading ? (
        <p>Loading…</p>
      ) : !clients?.length ? (
        <EmptyState title="No clients yet" hint="Add your first client to start tracking leads and opportunities against them." />
      ) : (
        <Card style={{ padding: 0 }}>
          <Table>
            <thead>
              <tr>
                <Th>Name</Th>
                <Th>Billing email</Th>
                <Th>Added</Th>
              </tr>
            </thead>
            <tbody>
              {clients.map((c) => (
                <tr key={c.id}>
                  <Td>{c.name}</Td>
                  <Td mono>{c.billing_email || "—"}</Td>
                  <Td mono>{new Date(c.created_at).toLocaleDateString()}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
    </div>
  );
}
