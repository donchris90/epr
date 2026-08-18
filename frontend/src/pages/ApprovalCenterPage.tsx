import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { apiClient } from "../api/client";
import { PageHeader, Card, Button, Table, Th, Td, Badge, ErrorBanner, EmptyState, Input, Select, Field, formatMoney } from "../components/ui";

interface WorkflowAction {
  id: string;
  step_number: number;
  action_type: string;
  actor_id: string;
  old_status: string;
  new_status: string;
  comment: string | null;
  delegated_to: string | null;
  created_at: string;
}

interface WorkflowInstance {
  id: string;
  workflow_id: string;
  module_name: string;
  entity_type: string;
  entity_id: string;
  status: string;
  current_step_number: number;
  amount: string | null;
  initiated_by: string;
  created_at: string;
  actions: WorkflowAction[];
}

interface OrgUser {
  id: string;
  email: string;
}

function getErrorMessage(err: any): string {
  return err?.response?.data?.detail || err?.response?.data?.title || "Something went wrong.";
}

function statusBadge(status: string) {
  const tones: Record<string, "green" | "brick" | "amber" | "neutral"> = {
    approved: "green",
    rejected: "brick",
    pending: "amber",
    cancelled: "neutral",
  };
  return <Badge tone={tones[status] ?? "neutral"}>{status}</Badge>;
}

function Overlay({ onClose, children }: { onClose: () => void; children: ReactNode }) {
  return (
    <div
      onClick={onClose}
      style={{ position: "fixed", inset: 0, background: "rgba(33, 26, 20, 0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100, padding: 24 }}
    >
      <div onClick={(e) => e.stopPropagation()} style={{ width: 560, maxHeight: "85vh", overflowY: "auto" }}>
        <Card>{children}</Card>
      </div>
    </div>
  );
}

/** Real approval detail -- full action history from the workflow
 * engine's own actions[] (built and tested earlier this session for
 * contract amendments, HSE permits, and EST budget revisions), real
 * Approve/Reject/Delegate/Comment actions calling the real backend.
 * Requester/actor names are resolved client-side against
 * GET /v1/org/members (no per-user lookup endpoint exists) -- an ID
 * with no matching member just shows as the raw ID rather than
 * guessing. */
function InstanceDetailModal({
  instance,
  members,
  onClose,
  onDone,
}: {
  instance: WorkflowInstance;
  members: Map<string, string>;
  onClose: () => void;
  onDone: () => void;
}) {
  const [comment, setComment] = useState("");
  const [delegateTo, setDelegateTo] = useState("");
  const [showDelegate, setShowDelegate] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<string | null>(null);

  function nameFor(userId: string) {
    return members.get(userId) ?? userId;
  }

  async function act(action: "approve" | "reject" | "cancel" | "comment") {
    if (action === "comment" && !comment.trim()) {
      setError("Enter a comment first.");
      return;
    }
    setSubmitting(action);
    setError(null);
    try {
      await apiClient.post(`/workflow/instances/${instance.id}/${action}`, { comment: comment.trim() || undefined });
      onDone();
    } catch (err: any) {
      setError(getErrorMessage(err));
    } finally {
      setSubmitting(null);
    }
  }

  async function delegate() {
    if (!delegateTo) {
      setError("Choose who to delegate to.");
      return;
    }
    setSubmitting("delegate");
    setError(null);
    try {
      await apiClient.post(`/workflow/instances/${instance.id}/delegate`, { delegate_to: delegateTo, comment: comment.trim() || undefined });
      onDone();
    } catch (err: any) {
      setError(getErrorMessage(err));
    } finally {
      setSubmitting(null);
    }
  }

  const isPending = instance.status === "pending";

  return (
    <Overlay onClose={onClose}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
        <div>
          <div style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>
            {instance.module_name.toUpperCase()} — {instance.entity_type.replace(/_/g, " ")}
          </div>
          <div style={{ fontWeight: 700, fontSize: 16 }}>Requested by {nameFor(instance.initiated_by)}</div>
        </div>
        {statusBadge(instance.status)}
      </div>

      {instance.amount && <div style={{ fontSize: 14, marginBottom: 12 }}>Amount: {formatMoney(instance.amount)}</div>}

      <div style={{ fontSize: 12, fontWeight: 600, color: "var(--sf-navy-600)", marginBottom: 8 }}>Approval history</div>
      <div style={{ border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", marginBottom: 16 }}>
        {instance.actions.length === 0 ? (
          <div style={{ padding: 12, fontSize: 13, color: "var(--sf-navy-400)" }}>No actions recorded yet.</div>
        ) : (
          instance.actions.map((a) => (
            <div key={a.id} style={{ padding: "10px 12px", borderBottom: "1px solid var(--sf-line)", fontSize: 13 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>
                  <strong>{nameFor(a.actor_id)}</strong> {a.action_type} (step {a.step_number})
                  {a.delegated_to && <> → delegated to {nameFor(a.delegated_to)}</>}
                </span>
                <span style={{ color: "var(--sf-navy-400)", fontSize: 12 }}>{new Date(a.created_at).toLocaleString()}</span>
              </div>
              {a.comment && <div style={{ color: "var(--sf-navy-600)", marginTop: 4 }}>"{a.comment}"</div>}
            </div>
          ))
        )}
      </div>

      {isPending && (
        <>
          <Field label="Comment (optional for approve/reject, required for comment-only)">
            <Input value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Add a note…" />
          </Field>

          {showDelegate && (
            <Field label="Delegate to">
              <Select value={delegateTo} onChange={(e) => setDelegateTo(e.target.value)}>
                <option value="">Select a person</option>
                {Array.from(members.entries()).map(([id, email]) => (
                  <option key={id} value={id}>
                    {email}
                  </option>
                ))}
              </Select>
            </Field>
          )}

          {error && <div style={{ color: "var(--sf-brick)", fontSize: 12, marginBottom: 10 }}>{error}</div>}

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Button onClick={() => act("approve")} disabled={!!submitting}>
              {submitting === "approve" ? "Approving…" : "Approve"}
            </Button>
            <Button variant="danger" onClick={() => act("reject")} disabled={!!submitting}>
              {submitting === "reject" ? "Rejecting…" : "Reject"}
            </Button>
            {showDelegate ? (
              <Button variant="secondary" onClick={delegate} disabled={!!submitting}>
                {submitting === "delegate" ? "Delegating…" : "Confirm Delegate"}
              </Button>
            ) : (
              <Button variant="secondary" onClick={() => setShowDelegate(true)} disabled={!!submitting}>
                Delegate
              </Button>
            )}
            <Button variant="ghost" onClick={() => act("comment")} disabled={!!submitting}>
              {submitting === "comment" ? "Posting…" : "Comment only"}
            </Button>
          </div>
        </>
      )}

      <div style={{ marginTop: 16, textAlign: "right" }}>
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      </div>
    </Overlay>
  );
}

export default function ApprovalCenterPage() {
  const [view, setView] = useState<"pending" | "all">("pending");
  const [instances, setInstances] = useState<WorkflowInstance[] | null>(null);
  const [members, setMembers] = useState<Map<string, string>>(new Map());
  const [statusFilter, setStatusFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<WorkflowInstance | null>(null);

  async function load() {
    setError(null);
    try {
      const url = view === "pending" ? "/workflow/instances/pending" : "/workflow/instances";
      const params = view === "all" && statusFilter ? { status: statusFilter } : undefined;
      const [instancesRes, membersRes] = await Promise.all([
        apiClient.get(url, { params }),
        apiClient.get("/org/members"),
      ]);
      setInstances(instancesRes.data.data);
      const map = new Map<string, string>();
      for (const u of membersRes.data.users as OrgUser[]) map.set(u.id, u.email);
      setMembers(map);
    } catch (err: any) {
      setError(getErrorMessage(err));
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, statusFilter]);

  function nameFor(userId: string) {
    return members.get(userId) ?? userId;
  }

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 24px" }}>
      <PageHeader eyebrow="Approvals" title="Approval Center" />

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <Button variant={view === "pending" ? "primary" : "secondary"} onClick={() => setView("pending")}>
          My Pending Approvals
        </Button>
        <Button variant={view === "all" ? "primary" : "secondary"} onClick={() => setView("all")}>
          All / History
        </Button>
        {view === "all" && (
          <div style={{ width: 160 }}>
            <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All statuses</option>
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
              <option value="cancelled">Cancelled</option>
            </Select>
          </div>
        )}
      </div>

      {error && <ErrorBanner title="Something went wrong" detail={error} onDismiss={() => setError(null)} />}

      <Card style={{ padding: 0 }}>
        {instances === null ? (
          <div style={{ padding: 24, fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>
        ) : instances.length === 0 ? (
          <EmptyState
            title={view === "pending" ? "No pending approvals" : "No approval history yet"}
            hint={view === "pending" ? "You're all caught up." : undefined}
          />
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Type</Th>
                <Th>Requested by</Th>
                <Th>Amount</Th>
                <Th>Status</Th>
                <Th>Date</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {instances.map((i) => (
                <tr key={i.id}>
                  <Td>
                    {i.module_name.toUpperCase()} — {i.entity_type.replace(/_/g, " ")}
                  </Td>
                  <Td>{nameFor(i.initiated_by)}</Td>
                  <Td mono>{i.amount ? formatMoney(i.amount) : "—"}</Td>
                  <Td>{statusBadge(i.status)}</Td>
                  <Td mono>{new Date(i.created_at).toLocaleDateString()}</Td>
                  <Td style={{ textAlign: "right" }}>
                    <Button variant="ghost" onClick={() => setSelected(i)}>
                      View
                    </Button>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      {selected && (
        <InstanceDetailModal
          instance={selected}
          members={members}
          onClose={() => setSelected(null)}
          onDone={() => {
            setSelected(null);
            load();
          }}
        />
      )}
    </div>
  );
}
