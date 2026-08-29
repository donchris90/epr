import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, ErrorBanner, Field, Input, Select } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import {
  useMaterialApprovals,
  useCreateMaterialApproval,
  useDecideMaterialApproval,
  useLabResults,
  useCreateLabResult,
  useRecordLabResultOutcome,
} from "./hooks";

function statusTone(status: string): "green" | "neutral" | "brick" | "amber" {
  if (status === "approved") return "green";
  if (status === "rejected") return "brick";
  return "amber";
}

const LAB_TEST_TYPES = ["concrete_cube_strength", "compaction_density", "asphalt_extraction", "other"];

/** Real material approvals and lab results, backed by the real
 * GET/POST endpoints added while closing this batch's own
 * frontend-backend gap audit (previously only POST existed for
 * either, no way to ever list one again). */
export default function MaterialApprovalsAndLabResultsPage() {
  return (
    <div>
      <PageHeader eyebrow="Quality Management" title="Material Approvals & Lab Results" />
      <div style={{ display: "grid", gap: 24 }}>
        <MaterialApprovalsSection />
        <LabResultsSection />
      </div>
    </div>
  );
}

function MaterialApprovalsSection() {
  const { data: approvals } = useMaterialApprovals();
  const createApproval = useCreateMaterialApproval();
  const decideApproval = useDecideMaterialApproval();
  const [reference, setReference] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createApproval.mutateAsync({ submittal_reference: reference });
      setReference("");
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <div>
      <h3 style={{ fontSize: 14, marginBottom: 12 }}>Material approvals</h3>
      <Card style={{ marginBottom: 16 }}>
        <form onSubmit={handleCreate} style={{ display: "flex", gap: 8 }}>
          <Input required placeholder="Submittal reference" value={reference} onChange={(e) => setReference(e.target.value)} style={{ flex: 1 }} />
          <Button type="submit" disabled={createApproval.isPending}>{createApproval.isPending ? "Submitting…" : "Submit"}</Button>
        </form>
        {error && <div style={{ marginTop: 12 }}><ErrorBanner title="Could not submit" detail={error} onDismiss={() => setError(null)} /></div>}
      </Card>
      <Card style={{ padding: 0 }}>
        {!approvals?.length ? (
          <EmptyState compact title="No material approvals submitted yet." />
        ) : (
          <Table>
            <thead><tr><Th>Submittal reference</Th><Th>Status</Th><Th /></tr></thead>
            <tbody>
              {approvals.map((a) => (
                <tr key={a.id}>
                  <Td>{a.submittal_reference}</Td>
                  <Td><Badge tone={statusTone(a.status)}>{a.status}</Badge></Td>
                  <Td style={{ textAlign: "right" }}>
                    {a.status === "submitted" && (
                      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                        <button onClick={() => decideApproval.mutate({ approvalId: a.id, decision: "approved" })} style={{ background: "none", border: "none", color: "var(--sf-green)", cursor: "pointer" }}>Approve</button>
                        <button onClick={() => decideApproval.mutate({ approvalId: a.id, decision: "rejected" })} style={{ background: "none", border: "none", color: "var(--sf-brick)", cursor: "pointer" }}>Reject</button>
                      </div>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}

function LabResultsSection() {
  const { data: results } = useLabResults();
  const createResult = useCreateLabResult();
  const recordOutcome = useRecordLabResultOutcome();
  const [form, setForm] = useState({ test_type: "concrete_cube_strength", result_value: "", acceptance_threshold: "" });
  const [error, setError] = useState<string | null>(null);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createResult.mutateAsync(form);
      setForm({ test_type: "concrete_cube_strength", result_value: "", acceptance_threshold: "" });
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <div>
      <h3 style={{ fontSize: 14, marginBottom: 12 }}>Lab results</h3>
      <Card style={{ marginBottom: 16 }}>
        <form onSubmit={handleCreate} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr 1fr auto", gap: 8 }}>
          <Select value={form.test_type} onChange={(e) => setForm({ ...form, test_type: e.target.value })}>
            {LAB_TEST_TYPES.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
          </Select>
          <Field label="Result value"><Input type="number" step="0.01" value={form.result_value} onChange={(e) => setForm({ ...form, result_value: e.target.value })} /></Field>
          <Field label="Acceptance threshold"><Input type="number" step="0.01" value={form.acceptance_threshold} onChange={(e) => setForm({ ...form, acceptance_threshold: e.target.value })} /></Field>
          <Button type="submit" disabled={createResult.isPending} style={{ height: 38, alignSelf: "end" }}>
            {createResult.isPending ? "Logging…" : "Log result"}
          </Button>
        </form>
        {error && <div style={{ marginTop: 12 }}><ErrorBanner title="Could not log result" detail={error} onDismiss={() => setError(null)} /></div>}
      </Card>
      <Card style={{ padding: 0 }}>
        {!results?.length ? (
          <EmptyState compact title="No lab results logged yet." />
        ) : (
          <Table>
            <thead><tr><Th>Test type</Th><Th>Result</Th><Th>Threshold</Th><Th>Outcome</Th></tr></thead>
            <tbody>
              {results.map((r) => (
                <tr key={r.id}>
                  <Td>{r.test_type.replace(/_/g, " ")}</Td>
                  <Td mono>{r.result_value ?? "—"} {r.unit ?? ""}</Td>
                  <Td mono>{r.acceptance_threshold ?? "—"}</Td>
                  <Td>
                    {r.pass_fail === null ? (
                      <div style={{ display: "flex", gap: 8 }}>
                        <button onClick={() => recordOutcome.mutate({ resultId: r.id, passFail: true })} style={{ background: "none", border: "none", color: "var(--sf-green)", cursor: "pointer" }}>Pass</button>
                        <button onClick={() => recordOutcome.mutate({ resultId: r.id, passFail: false })} style={{ background: "none", border: "none", color: "var(--sf-brick)", cursor: "pointer" }}>Fail</button>
                      </div>
                    ) : (
                      <Badge tone={r.pass_fail ? "green" : "brick"}>{r.pass_fail ? "Pass" : "Fail"}</Badge>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}
