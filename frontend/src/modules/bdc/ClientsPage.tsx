import { useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader, Card, Button, Input, Field } from "../../components/ui";
import { DataTable } from "../../components/DataTable";
import { QueryState } from "../../components/QueryState";
import { useClients, useCreateClient } from "./hooks";
import { useToast } from "../../lib/toast";
import { getErrorMessage } from "../../api/client";
import type { Client } from "./types";

export default function ClientsPage() {
  const query = useClients();
  const createClient = useCreateClient();
  const toast = useToast();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [address, setAddress] = useState("");
  const [notes, setNotes] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    try {
      await createClient.mutateAsync({
        name,
        billing_email: email || undefined,
        billing_address: address || undefined,
        notes: notes || undefined,
      });
      toast.success(`"${name}" was added.`);
      setName("");
      setEmail("");
      setAddress("");
      setNotes("");
      setShowForm(false);
    } catch (err) {
      setFormError(getErrorMessage(err));
    }
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
              <Field label="Client name" required>
                <Input required value={name} onChange={(e) => setName(e.target.value)} placeholder="Acme Construction Ltd" />
              </Field>
              <Field label="Billing email (optional)">
                <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="accounts@acme.com" />
              </Field>
              <Field label="Billing address (optional)">
                <Input value={address} onChange={(e) => setAddress(e.target.value)} placeholder="123 Marina Rd, Lagos" />
              </Field>
              <Field label="Notes (optional)">
                <Input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Key contacts, preferences…" />
              </Field>
            </div>
            {formError && (
              <div role="alert" style={{ color: "var(--sf-brick)", fontSize: 12, marginBottom: 12 }}>
                {formError}
              </div>
            )}
            <Button type="submit" disabled={createClient.isPending}>
              {createClient.isPending ? "Saving…" : "Save client"}
            </Button>
          </form>
        </Card>
      )}

      <Card style={{ padding: query.isLoading || query.isError ? 0 : undefined }}>
        <QueryState
          query={query}
          variant="table"
          loadingLabel="Loading clients"
          emptyTitle="No clients yet"
          emptyHint="Add your first client to start tracking leads and opportunities against them."
          emptyAction={<Button onClick={() => setShowForm(true)}>New client</Button>}
        >
          {(clients) => (
            <DataTable
              columns={[
                {
                  key: "name",
                  header: "Name",
                  render: (c: Client) => <Link to={`/business-development/clients/${c.id}`}>{c.name}</Link>,
                  sortValue: (c: Client) => c.name.toLowerCase(),
                },
                { key: "email", header: "Billing email", render: (c: Client) => c.billing_email || "—", sortValue: (c: Client) => c.billing_email ?? "" },
                {
                  key: "added",
                  header: "Added",
                  render: (c: Client) => <span className="sf-mono">{new Date(c.created_at).toLocaleDateString()}</span>,
                  sortValue: (c: Client) => c.created_at,
                },
              ]}
              rows={clients}
              getRowId={(c) => c.id}
              exportFilename="clients"
              searchFields={(c) => [c.name, c.billing_email]}
              searchPlaceholder="Search clients…"
              emptyTitle="No clients match your search"
              rowActions={(c) => (
                <Link to={`/business-development/clients/${c.id}`} style={{ fontSize: 12, fontWeight: 600 }}>
                  View →
                </Link>
              )}
            />
          )}
        </QueryState>
      </Card>
    </div>
  );
}
