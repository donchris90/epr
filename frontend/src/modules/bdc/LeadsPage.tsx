import { useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader, Card, Button, Input, Field, Select, Badge, formatMoney } from "../../components/ui";
import { DataTable } from "../../components/DataTable";
import { QueryState } from "../../components/QueryState";
import { useClients } from "./hooks";
import { useLeads, useCreateLead, useConvertLead } from "./hooks";
import { useToast } from "../../lib/toast";
import { getErrorMessage } from "../../api/client";
import type { Lead } from "./types";

export default function LeadsPage() {
  const query = useLeads();
  const { data: clients } = useClients();
  const createLead = useCreateLead();
  const convertLead = useConvertLead();
  const toast = useToast();

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [source, setSource] = useState("");
  const [estimatedValue, setEstimatedValue] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [convertingLeadId, setConvertingLeadId] = useState<string | null>(null);
  const [convertClientId, setConvertClientId] = useState("");

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    try {
      await createLead.mutateAsync({ name, source: source || undefined, estimated_value: estimatedValue || undefined });
      toast.success(`Lead "${name}" was logged.`);
      setName("");
      setSource("");
      setEstimatedValue("");
      setShowForm(false);
    } catch (err) {
      setFormError(getErrorMessage(err));
    }
  }

  async function handleConvert(leadId: string) {
    if (!convertClientId) return;
    try {
      await convertLead.mutateAsync({ leadId, clientId: convertClientId });
      toast.success("Lead converted to an opportunity.");
      setConvertingLeadId(null);
      setConvertClientId("");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
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
            <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
              <Field label="Lead name" required>
                <Input required value={name} onChange={(e) => setName(e.target.value)} placeholder="New Highway Extension" />
              </Field>
              <Field label="Source (optional)">
                <Input value={source} onChange={(e) => setSource(e.target.value)} placeholder="Referral, tender board, etc." />
              </Field>
              <Field label="Estimated value (optional)">
                <Input value={estimatedValue} onChange={(e) => setEstimatedValue(e.target.value)} placeholder="0.00" />
              </Field>
            </div>
            {formError && (
              <div role="alert" style={{ color: "var(--sf-brick)", fontSize: 12, marginBottom: 12 }}>
                {formError}
              </div>
            )}
            <Button type="submit" disabled={createLead.isPending}>
              {createLead.isPending ? "Saving…" : "Save lead"}
            </Button>
          </form>
        </Card>
      )}

      <Card style={{ padding: query.isLoading || query.isError ? 0 : undefined }}>
        <QueryState
          query={query}
          variant="table"
          loadingLabel="Loading leads"
          emptyTitle="No leads yet"
          emptyHint="Log a lead as soon as you hear about a potential opportunity."
          emptyAction={<Button onClick={() => setShowForm(true)}>New lead</Button>}
        >
          {(leads) => (
            <DataTable
              columns={[
                {
                  key: "name",
                  header: "Name",
                  render: (l: Lead) => <Link to={`/business-development/leads/${l.id}`}>{l.name}</Link>,
                  sortValue: (l: Lead) => l.name.toLowerCase(),
                },
                { key: "source", header: "Source", render: (l: Lead) => l.source || "—", sortValue: (l: Lead) => l.source ?? "" },
                {
                  key: "value",
                  header: "Est. value",
                  render: (l: Lead) => <span className="sf-mono">{formatMoney(l.estimated_value)}</span>,
                  sortValue: (l: Lead) => Number(l.estimated_value ?? 0),
                  align: "right" as const,
                },
                {
                  key: "status",
                  header: "Status",
                  render: (l: Lead) => <Badge tone={l.status === "open" ? "steel" : "neutral"}>{l.status}</Badge>,
                  sortValue: (l: Lead) => l.status,
                },
              ]}
              rows={leads}
              getRowId={(l) => l.id}
              exportFilename="leads"
              searchFields={(l) => [l.name, l.source]}
              searchPlaceholder="Search leads…"
              emptyTitle="No leads match your search"
              rowActions={(l) =>
                l.status === "open" ? (
                  convertingLeadId === l.id ? (
                    <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                      <Select value={convertClientId} onChange={(e) => setConvertClientId(e.target.value)} aria-label="Select client to convert into">
                        <option value="">Select client…</option>
                        {clients?.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        ))}
                      </Select>
                      <Button variant="secondary" onClick={() => handleConvert(l.id)} disabled={!convertClientId || convertLead.isPending}>
                        Go
                      </Button>
                    </div>
                  ) : (
                    <Button variant="ghost" onClick={() => setConvertingLeadId(l.id)}>
                      Convert to opportunity →
                    </Button>
                  )
                ) : null
              }
            />
          )}
        </QueryState>
      </Card>
    </div>
  );
}
