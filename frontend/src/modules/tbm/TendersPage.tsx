import { useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader, Card, Button, Table, Th, Td, EmptyState, Input, Select, Field, Badge } from "../../components/ui";
import { useOpportunities } from "../bdc/hooks";
import { useTenders, useCreateTender } from "./hooks";

const STAGE_TONE: Record<string, "neutral" | "amber" | "steel" | "green" | "brick"> = {
  draft: "neutral",
  in_estimate: "steel",
  in_approval: "amber",
  submitted: "steel",
  awarded: "green",
  lost: "brick",
};

export default function TendersPage() {
  const { data: tenders, isLoading } = useTenders();
  const { data: opportunities } = useOpportunities();
  const createTender = useCreateTender();

  const [showForm, setShowForm] = useState(false);
  const [opportunityId, setOpportunityId] = useState("");
  const [referenceNumber, setReferenceNumber] = useState("");

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    await createTender.mutateAsync({ opportunity_id: opportunityId, reference_number: referenceNumber });
    setOpportunityId("");
    setReferenceNumber("");
    setShowForm(false);
  }

  return (
    <div>
      <PageHeader
        eyebrow="Tender-to-Contract"
        title="Tenders"
        action={<Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "Register tender"}</Button>}
      />

      {showForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreate}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <Field label="Opportunity">
                <Select required value={opportunityId} onChange={(e) => setOpportunityId(e.target.value)}>
                  <option value="">Select opportunity…</option>
                  {opportunities?.map((o: any) => (
                    <option key={o.id} value={o.id}>
                      {o.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Reference number">
                <Input required value={referenceNumber} onChange={(e) => setReferenceNumber(e.target.value)} placeholder="TND-2026-001" />
              </Field>
            </div>
            <Button type="submit" disabled={createTender.isPending}>
              {createTender.isPending ? "Saving…" : "Register tender"}
            </Button>
          </form>
        </Card>
      )}

      {isLoading ? (
        <p>Loading…</p>
      ) : !tenders?.length ? (
        <EmptyState title="No tenders yet" hint="Register a tender against a qualified opportunity to begin pricing and submission." />
      ) : (
        <Card style={{ padding: 0 }}>
          <Table>
            <thead>
              <tr>
                <Th>Reference</Th>
                <Th>Status</Th>
                <Th>Deadline</Th>
                <Th></Th>
              </tr>
            </thead>
            <tbody>
              {tenders.map((t: any) => (
                <tr key={t.id}>
                  <Td mono>{t.reference_number}</Td>
                  <Td>
                    <Badge tone={STAGE_TONE[t.status] || "neutral"}>{t.status.replace(/_/g, " ")}</Badge>
                  </Td>
                  <Td mono>{t.submission_deadline ? new Date(t.submission_deadline).toLocaleDateString() : "—"}</Td>
                  <Td>
                    <Link to={`/tenders/${t.id}`} style={{ fontSize: 12, fontWeight: 600 }}>
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
