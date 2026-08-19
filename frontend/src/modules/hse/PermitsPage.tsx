import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input, Field, ErrorBanner } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import { useRiskAssessments, useCreateRiskAssessment, usePermits, useIssuePermit, useActivatePermit, useClosePermit } from "./hooks";

const STATUS_TONE: Record<string, "neutral" | "amber" | "steel" | "green" | "brick"> = {
  pending: "amber",
  active: "green",
  closed: "neutral",
  expired: "brick",
};

export default function PermitsPage() {
  const { data: riskAssessments } = useRiskAssessments();
  const createRA = useCreateRiskAssessment();
  const [raForm, setRaForm] = useState({ activity_or_area: "", risk_level: "medium" });
  const [showRaForm, setShowRaForm] = useState(false);

  const { data: permits, isLoading } = usePermits();
  const issuePermit = useIssuePermit();
  const activatePermit = useActivatePermit();
  const closePermit = useClosePermit();
  const [permitForm, setPermitForm] = useState({ project_id: "", permit_type: "hot_work", risk_assessment_id: "" });
  const [showPermitForm, setShowPermitForm] = useState(false);
  const [permitError, setPermitError] = useState<string | null>(null);

  async function handleCreateRA(e: React.FormEvent) {
    e.preventDefault();
    await createRA.mutateAsync(raForm);
    setRaForm({ activity_or_area: "", risk_level: "medium" });
    setShowRaForm(false);
  }

  async function handleIssuePermit(e: React.FormEvent) {
    e.preventDefault();
    setPermitError(null);
    try {
      await issuePermit.mutateAsync({ ...permitForm, risk_assessment_id: permitForm.risk_assessment_id || undefined });
      setPermitForm({ project_id: "", permit_type: "hot_work", risk_assessment_id: "" });
      setShowPermitForm(false);
    } catch (err) {
      // Business rule: an expired risk assessment or non-current
      // worker training blocks issuance -- surfaced here directly.
      setPermitError(getErrorMessage(err));
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Health, Safety & Environment"
        title="Permits to Work"
        action={
          <div style={{ display: "flex", gap: 8 }}>
            <Button variant="secondary" onClick={() => setShowRaForm((v) => !v)}>
              {showRaForm ? "Cancel" : "New risk assessment"}
            </Button>
            <Button onClick={() => setShowPermitForm((v) => !v)}>{showPermitForm ? "Cancel" : "Issue permit"}</Button>
          </div>
        }
      />

      {showRaForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreateRA} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr auto", gap: 12 }}>
            <Field label="Activity / area">
              <Input required value={raForm.activity_or_area} onChange={(e) => setRaForm({ ...raForm, activity_or_area: e.target.value })} />
            </Field>
            <Field label="Risk level">
              <select
                value={raForm.risk_level}
                onChange={(e) => setRaForm({ ...raForm, risk_level: e.target.value })}
                style={{ padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, background: "#fff" }}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </Field>
            <Button type="submit" disabled={createRA.isPending} style={{ height: 38, alignSelf: "end" }}>Add</Button>
          </form>
        </Card>
      )}

      {showPermitForm && (
        <Card style={{ marginBottom: 20 }}>
          <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
            Blocked if the linked risk assessment has expired, or if worker training isn't recorded as current.
          </p>
          {permitError && <ErrorBanner title="Cannot issue permit" detail={permitError} onDismiss={() => setPermitError(null)} />}
          <form onSubmit={handleIssuePermit} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr 1.5fr auto", gap: 12 }}>
            <Input required placeholder="Project ID" value={permitForm.project_id} onChange={(e) => setPermitForm({ ...permitForm, project_id: e.target.value })} />
            <select
              value={permitForm.permit_type}
              onChange={(e) => setPermitForm({ ...permitForm, permit_type: e.target.value })}
              style={{ padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, background: "#fff" }}
            >
              <option value="hot_work">Hot work</option>
              <option value="confined_space">Confined space</option>
              <option value="working_at_height">Working at height</option>
              <option value="excavation">Excavation</option>
            </select>
            <select
              value={permitForm.risk_assessment_id}
              onChange={(e) => setPermitForm({ ...permitForm, risk_assessment_id: e.target.value })}
              style={{ padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, background: "#fff" }}
            >
              <option value="">Risk assessment (optional)…</option>
              {(riskAssessments ?? []).map((r: any) => (
                <option key={r.id} value={r.id}>{r.activity_or_area}</option>
              ))}
            </select>
            <Button type="submit" disabled={issuePermit.isPending} style={{ height: 38, alignSelf: "end" }}>Issue</Button>
          </form>
        </Card>
      )}

      {isLoading ? (
        <p>Loading…</p>
      ) : !permits?.length ? (
        <EmptyState title="No permits issued" hint="Issue a permit to work before hazardous activities begin." />
      ) : (
        <Card style={{ padding: 0 }}>
          <Table>
            <thead><tr><Th>Type</Th><Th>Status</Th><Th></Th></tr></thead>
            <tbody>
              {permits.map((p: any) => (
                <tr key={p.id}>
                  <Td>{p.permit_type.replace(/_/g, " ")}</Td>
                  <Td><Badge tone={STATUS_TONE[p.status] ?? "neutral"}>{p.status}</Badge></Td>
                  <Td>
                    <div style={{ display: "flex", gap: 10 }}>
                      {p.status === "pending" && (
                        <button onClick={() => activatePermit.mutate(p.id)} style={{ background: "none", border: "none", color: "var(--sf-green)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
                          Activate
                        </button>
                      )}
                      {p.status === "active" && (
                        <button onClick={() => closePermit.mutate(p.id)} style={{ background: "none", border: "none", color: "var(--sf-steel)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
                          Formally close
                        </button>
                      )}
                    </div>
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
