import { useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input, Field } from "../../components/ui";
import { ContractSelect } from "../../components/ContractSelect";
import { useCertificates, useCreateCertificate } from "./hooks";

const STATUS_TONE: Record<string, "neutral" | "amber" | "steel" | "green" | "brick"> = {
  draft: "neutral",
  submitted: "amber",
  client_approved: "green",
  rejected: "brick",
};

export default function CertificatesPage() {
  const [statusFilter, setStatusFilter] = useState("");
  const { data: certs, isLoading } = useCertificates(statusFilter || undefined);
  const createCert = useCreateCertificate();

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ contract_id: "", certificate_number: "" });

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    await createCert.mutateAsync({ contract_id: form.contract_id || undefined, certificate_number: form.certificate_number });
    setForm({ contract_id: "", certificate_number: "" });
    setShowForm(false);
  }

  return (
    <div>
      <PageHeader
        eyebrow="Client Billing"
        title="Progress Certificates"
        action={<Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "New certificate"}</Button>}
      />

      <div style={{ marginBottom: 20, maxWidth: 280 }}>
        <Field label="Filter by status">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, width: "100%", background: "#fff" }}
          >
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="submitted">Submitted</option>
            <option value="client_approved">Client approved</option>
            <option value="rejected">Rejected</option>
          </select>
        </Field>
      </div>

      {showForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreate} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr auto", gap: 16 }}>
            <Field label="Contract (optional)">
              <ContractSelect value={form.contract_id} onChange={(contract_id) => setForm({ ...form, contract_id })} />
            </Field>
            <Field label="Certificate number">
              <Input required value={form.certificate_number} onChange={(e) => setForm({ ...form, certificate_number: e.target.value })} />
            </Field>
            <Button type="submit" disabled={createCert.isPending} style={{ height: 38, alignSelf: "end" }}>
              Create
            </Button>
          </form>
        </Card>
      )}

      {isLoading ? (
        <p>Loading…</p>
      ) : !certs?.length ? (
        <EmptyState title="No certificates yet" hint="Create one and add certified quantities against the BOQ to bill a client." />
      ) : (
        <Card style={{ padding: 0 }}>
          <Table>
            <thead>
              <tr>
                <Th>Number</Th>
                <Th>Gross certified</Th>
                <Th>Net payable</Th>
                <Th>Status</Th>
                <Th></Th>
              </tr>
            </thead>
            <tbody>
              {certs.map((c: any) => (
                <tr key={c.id}>
                  <Td mono>{c.certificate_number}</Td>
                  <Td mono>{c.gross_certified_amount}</Td>
                  <Td mono>{c.net_payable}</Td>
                  <Td>
                    <Badge tone={STATUS_TONE[c.status] ?? "neutral"}>{c.status.replace(/_/g, " ")}</Badge>
                  </Td>
                  <Td>
                    <Link to={`certificates/${c.id}`} style={{ fontSize: 12, fontWeight: 600 }}>
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
