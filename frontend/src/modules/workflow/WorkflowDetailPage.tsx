import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { apiClient } from "../../api/client";
import { useWorkflowDefinition, getWorkflowVersionHistory, activateWorkflowDefinition, deactivateWorkflowDefinition } from "./hooks";
import { hasPermission } from "../../lib/permissions";
import type { WorkflowDefinition } from "./types";
import { PageHeader, Card, Table, Th, Td, Badge, Button, ErrorBanner } from "../../components/ui";

function getErrorMessage(err: any): string {
  return err?.response?.data?.detail || err?.response?.data?.title || "Something went wrong.";
}

function approverLabel(step: WorkflowDefinition["steps"][number], members: Map<string, string>, roles: Map<string, string>) {
  if (step.approver_type === "specific_user") return step.specific_user_id ? members.get(step.specific_user_id) ?? step.specific_user_id : "—";
  return step.required_role_id ? roles.get(step.required_role_id) ?? step.required_role_id : "—";
}

/** Real Workflow Detail -- backed by GET /v1/workflow/definitions/<id>
 * (app/workflow/routes.py). Steps are shown read-only here (the
 * editable canvas lives in WorkflowBuilderPage); version history
 * comes from the same real GET /v1/workflow/definitions endpoint
 * filtered by this definition's own module_name/entity_type -- old
 * versions are never deleted (app/workflow/services.py's own
 * docstring), so this is genuinely real data, not synthesized. */
export default function WorkflowDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { definition, loading, error, reload } = useWorkflowDefinition(id);
  const [history, setHistory] = useState<WorkflowDefinition[] | null>(null);
  const [members, setMembers] = useState<Map<string, string>>(new Map());
  const [roles, setRoles] = useState<Map<string, string>>(new Map());
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const canManage = hasPermission("workflow:admin");

  useEffect(() => {
    Promise.all([apiClient.get("/org/members"), apiClient.get("/org/roles")])
      .then(([membersRes, rolesRes]) => {
        const m = new Map<string, string>();
        for (const u of membersRes.data.users) m.set(u.id, u.email);
        setMembers(m);
        const r = new Map<string, string>();
        for (const role of rolesRes.data.data) r.set(role.id, role.name);
        setRoles(r);
      })
      .catch(() => {});
  }, []);

  // Deliberately narrower than the full definition object: this only
  // cares about module_name/entity_type, and re-running on every field
  // change (version, updated_at, ...) would be wasted real network calls.
  useEffect(() => {
    if (!definition) return;
    getWorkflowVersionHistory(definition.module_name, definition.entity_type)
      .then(setHistory)
      .catch(() => setHistory(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [definition?.module_name, definition?.entity_type]);

  async function handleActivate() {
    if (!definition) return;
    setBusy(true);
    setActionError(null);
    try {
      await activateWorkflowDefinition(definition.id);
      reload();
    } catch (err: any) {
      setActionError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleDeactivate() {
    if (!definition) return;
    setBusy(true);
    setActionError(null);
    try {
      await deactivateWorkflowDefinition(definition.id);
      reload();
    } catch (err: any) {
      setActionError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <div style={{ padding: 32, fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>;
  if (error) return <div style={{ padding: 32 }}><ErrorBanner title="Something went wrong" detail={error} /></div>;
  if (!definition) return null;

  const stepGroups = Array.from(new Set(definition.steps.map((s) => s.step_number))).sort((a, b) => a - b);

  return (
    <div style={{ maxWidth: 1000, margin: "0 auto", padding: "32px 24px" }}>
      <PageHeader
        eyebrow={`v${definition.version} · ${definition.module_name} / ${definition.entity_type}`}
        title={definition.workflow_name}
        action={
          canManage ? (
            <div style={{ display: "flex", gap: 8 }}>
              {!definition.active ? (
                <Button onClick={handleActivate} disabled={busy}>
                  {busy ? "Publishing…" : "Publish / Activate"}
                </Button>
              ) : (
                <Button variant="secondary" onClick={handleDeactivate} disabled={busy}>
                  {busy ? "Deactivating…" : "Deactivate"}
                </Button>
              )}
              <Link to={`/workflows/new?module_name=${definition.module_name}&entity_type=${definition.entity_type}`}>
                <Button variant="ghost">New version</Button>
              </Link>
            </div>
          ) : undefined
        }
      />

      {actionError && <ErrorBanner title="Something went wrong" detail={actionError} onDismiss={() => setActionError(null)} />}

      <Card>
        <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 20, marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase" }}>Status</div>
            <Badge tone={definition.active ? "green" : "neutral"}>{definition.active ? "Active" : "Draft"}</Badge>
          </div>
          <div>
            <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase" }}>Created by</div>
            <div>{definition.created_by ? members.get(definition.created_by) ?? definition.created_by : "—"}</div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase" }}>Last changed</div>
            <div>
              {new Date(definition.updated_at).toLocaleString()}
              {definition.updated_by && <span style={{ color: "var(--sf-navy-400)" }}> by {members.get(definition.updated_by) ?? definition.updated_by}</span>}
            </div>
          </div>
        </div>
        {definition.description && <p style={{ fontSize: 13, color: "var(--sf-navy-600)" }}>{definition.description}</p>}
      </Card>

      <div style={{ marginTop: 24 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Trigger</h3>
        <Card>
          <div style={{ fontSize: 13 }}>
            Runs whenever a real <strong className="sf-mono">{definition.entity_type}</strong> is submitted in the{" "}
            <strong className="sf-mono">{definition.module_name}</strong> module.
          </div>
        </Card>
      </div>

      <div style={{ marginTop: 24 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Approval steps</h3>
        {stepGroups.map((stepNumber) => {
          const steps = definition.steps.filter((s) => s.step_number === stepNumber);
          const isParallel = steps.length > 1;
          return (
            <Card key={stepNumber} style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase", marginBottom: 8 }}>
                Step {stepNumber} {isParallel && <Badge tone="steel">Parallel — all must approve</Badge>}
              </div>
              {steps.map((step) => (
                <div key={step.id ?? step.step_number} style={{ padding: "8px 0", borderTop: "1px solid var(--sf-line)" }}>
                  <div style={{ fontWeight: 600 }}>{step.name}</div>
                  <div style={{ fontSize: 12, color: "var(--sf-navy-600)" }}>
                    Approver: {step.approver_type === "specific_user" ? "Specific user" : "Role"} —{" "}
                    {approverLabel(step, members, roles)}
                  </div>
                  {(step.minimum_amount || step.maximum_amount) && (
                    <div style={{ fontSize: 12, color: "var(--sf-navy-600)" }}>
                      Applies only when amount is{" "}
                      {step.minimum_amount && `≥ ₦${Number(step.minimum_amount).toLocaleString()}`}
                      {step.minimum_amount && step.maximum_amount && " and "}
                      {step.maximum_amount && `≤ ₦${Number(step.maximum_amount).toLocaleString()}`}
                    </div>
                  )}
                  {step.reject_to_step != null && (
                    <div style={{ fontSize: 12, color: "var(--sf-navy-600)" }}>On rejection, returns to step {step.reject_to_step} for rework</div>
                  )}
                  {step.timeout_hours && (
                    <div style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>
                      Timeout: {step.timeout_hours}h {step.auto_escalate && "(auto-escalate — recorded, not yet enforced by a scheduler)"}
                    </div>
                  )}
                </div>
              ))}
            </Card>
          );
        })}
      </div>

      <div style={{ marginTop: 24 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Notifications</h3>
        <Card>
          <p style={{ fontSize: 13, color: "var(--sf-navy-600)" }}>
            Automatic, not separately configurable: every approver for the current step is emailed when their turn comes up, and
            the person who submitted the request is emailed when it's fully approved or rejected.
          </p>
        </Card>
      </div>

      <div style={{ marginTop: 24 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Version history</h3>
        <Card style={{ padding: 0 }}>
          {!history ? (
            <div style={{ padding: 16, fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>Version</Th>
                  <Th>Status</Th>
                  <Th>Created by</Th>
                  <Th>Created</Th>
                  <Th />
                </tr>
              </thead>
              <tbody>
                {history.map((h) => (
                  <tr key={h.id}>
                    <Td mono>
                      v{h.version} {h.id === definition.id && <Badge tone="amber">Viewing</Badge>}
                    </Td>
                    <Td>
                      <Badge tone={h.active ? "green" : "neutral"}>{h.active ? "Active" : "Draft"}</Badge>
                    </Td>
                    <Td>{h.created_by ? members.get(h.created_by) ?? h.created_by : "—"}</Td>
                    <Td mono>{new Date(h.created_at).toLocaleDateString()}</Td>
                    <Td style={{ textAlign: "right" }}>
                      {h.id !== definition.id && (
                        <Button variant="ghost" onClick={() => navigate(`/workflows/${h.id}`)}>
                          View
                        </Button>
                      )}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>
      </div>
    </div>
  );
}
