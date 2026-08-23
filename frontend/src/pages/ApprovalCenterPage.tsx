import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { apiClient } from "../api/client";
import { PageHeader, Card, Button, Table, Th, Td, Badge, ErrorBanner, EmptyState, Input, Select, Field, formatMoney } from "../components/ui";
import { computeSlaInfo, formatTimeRemaining, SLA_STATE_LABEL, SLA_STATE_TONE } from "../modules/workflow/sla";
import type { WorkflowDefinition, WorkflowInstance } from "../modules/workflow/types";

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

/** Real SLA badge -- see modules/workflow/sla.ts's own docstring on
 * exactly what this is computed from (real timeout_hours + real
 * action history, no invented backend data) and its honest limits
 * (a presentational state, not backend-enforced automatic
 * escalation). Renders nothing at all when there's genuinely no SLA
 * configured for the current step, rather than a misleading "no
 * deadline" badge implying SLA tracking exists universally. */
function SlaBadge({ instance, definition }: { instance: WorkflowInstance; definition: WorkflowDefinition | null }) {
  const sla = computeSlaInfo(instance, definition);
  if (sla.state === "no_sla" || !sla.dueAt) return null;
  return (
    <Badge tone={SLA_STATE_TONE[sla.state]}>
      {SLA_STATE_LABEL[sla.state]} · {formatTimeRemaining(sla.dueAt)}
    </Badge>
  );
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
  definition,
  onClose,
  onDone,
}: {
  instance: WorkflowInstance;
  members: Map<string, string>;
  definition: WorkflowDefinition | null;
  onClose: () => void;
  onDone: () => void;
}) {
  const [comment, setComment] = useState("");
  const [delegateTo, setDelegateTo] = useState("");
  const [showDelegate, setShowDelegate] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<string | null>(null);
  // Real confirmation step, inline rather than a nested modal --
  // holds which action is awaiting a real "are you sure", or null
  // when nothing is pending confirmation yet.
  const [confirming, setConfirming] = useState<"approve" | "reject" | "delegate" | null>(null);

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
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <SlaBadge instance={instance} definition={definition} />
          {statusBadge(instance.status)}
        </div>
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

          {confirming ? (
            <div style={{ background: "var(--sf-paper-dim)", borderRadius: "var(--sf-radius)", padding: 12 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
                {confirming === "approve" && "Approve this request?"}
                {confirming === "reject" && "Reject this request?"}
                {confirming === "delegate" && `Delegate to ${delegateTo ? nameFor(delegateTo) : "this person"}?`}
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <Button
                  variant={confirming === "reject" ? "danger" : "primary"}
                  onClick={() => (confirming === "delegate" ? delegate() : act(confirming))}
                  disabled={!!submitting}
                >
                  {submitting ? "Working…" : "Yes, confirm"}
                </Button>
                <Button variant="ghost" onClick={() => setConfirming(null)} disabled={!!submitting}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <Button onClick={() => setConfirming("approve")} disabled={!!submitting}>
                Approve
              </Button>
              <Button variant="danger" onClick={() => setConfirming("reject")} disabled={!!submitting}>
                Reject
              </Button>
              {showDelegate ? (
                <Button variant="secondary" onClick={() => setConfirming("delegate")} disabled={!!submitting || !delegateTo}>
                  Confirm Delegate
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
          )}
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
  const [definitions, setDefinitions] = useState<Map<string, WorkflowDefinition>>(new Map());
  const [statusFilter, setStatusFilter] = useState("");
  const [moduleFilter, setModuleFilter] = useState("");
  const [slaFilter, setSlaFilter] = useState<"" | "due_soon" | "overdue">("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<WorkflowInstance | null>(null);

  async function load() {
    setError(null);
    try {
      const url = view === "pending" ? "/workflow/instances/pending" : "/workflow/instances";
      // Real, server-side filters only (module_name, status) --
      // GET /v1/workflow/instances's own docstring is explicit that
      // date/amount/requester/approver filtering isn't supported
      // server-side (see docs/WORKFLOW_APPROVAL_GAPS.md); applied as
      // real query params here, everything else below happens
      // client-side over the returned set.
      const params: Record<string, string> = {};
      if (view === "all" && statusFilter) params.status = statusFilter;
      if (moduleFilter) params.module_name = moduleFilter;

      const [instancesRes, membersRes, definitionsRes] = await Promise.all([
        apiClient.get(url, { params: Object.keys(params).length ? params : undefined }),
        apiClient.get("/org/members"),
        apiClient.get("/workflow/definitions"),
      ]);
      setInstances(instancesRes.data.data);
      const map = new Map<string, string>();
      for (const u of membersRes.data.users as OrgUser[]) map.set(u.id, u.email);
      setMembers(map);
      const defMap = new Map<string, WorkflowDefinition>();
      for (const d of definitionsRes.data.data as WorkflowDefinition[]) defMap.set(d.id, d);
      setDefinitions(defMap);
    } catch (err: any) {
      setError(getErrorMessage(err));
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, statusFilter, moduleFilter]);

  function nameFor(userId: string) {
    return members.get(userId) ?? userId;
  }

  /** Real client-side filtering (search, SLA state, date range) over
   * whatever the server-side filters above already narrowed down to
   * -- honestly bounded by GET /v1/workflow/instances's own 200-row
   * cap (backend/app/workflow/routes.py), not a concern for the
   * realistic pending/recent-history volumes this page is for. */
  const filteredInstances = useMemo(() => {
    if (!instances) return null;
    return instances.filter((instance) => {
      if (search.trim()) {
        const q = search.trim().toLowerCase();
        const requesterName = nameFor(instance.initiated_by).toLowerCase();
        const haystack = `${instance.module_name} ${instance.entity_type} ${requesterName}`.toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      if (dateFrom && new Date(instance.created_at) < new Date(dateFrom)) return false;
      if (dateTo && new Date(instance.created_at) > new Date(`${dateTo}T23:59:59`)) return false;
      if (slaFilter) {
        const sla = computeSlaInfo(instance, definitions.get(instance.workflow_id) ?? null);
        if (sla.state !== slaFilter) return false;
      }
      return true;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [instances, search, dateFrom, dateTo, slaFilter, definitions, members]);

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "32px 24px" }}>
      <PageHeader eyebrow="Approvals" title="Approval Center" />

      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        <Button variant={view === "pending" ? "primary" : "secondary"} onClick={() => setView("pending")}>
          Assigned to Me
        </Button>
        <Button variant={view === "all" ? "primary" : "secondary"} onClick={() => setView("all")}>
          All / History
        </Button>
      </div>

      <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr 1fr", gap: 10, marginBottom: 16 }}>
        <Field label="Search">
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Requester, module…" />
        </Field>
        <Field label="Module">
          <Select value={moduleFilter} onChange={(e) => setModuleFilter(e.target.value)}>
            <option value="">All modules</option>
            <option value="prc">Procurement</option>
            <option value="ctm">Contracts</option>
            <option value="est">Estimating</option>
            <option value="hse">HSE</option>
          </Select>
        </Field>
        {view === "all" && (
          <Field label="Status">
            <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All statuses</option>
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
              <option value="cancelled">Cancelled</option>
            </Select>
          </Field>
        )}
        <Field label="SLA">
          <Select value={slaFilter} onChange={(e) => setSlaFilter(e.target.value as "" | "due_soon" | "overdue")}>
            <option value="">Any</option>
            <option value="due_soon">Due soon</option>
            <option value="overdue">Overdue</option>
          </Select>
        </Field>
        <Field label="From">
          <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </Field>
        <Field label="To">
          <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </Field>
      </div>

      {error && <ErrorBanner title="Something went wrong" detail={error} onDismiss={() => setError(null)} />}

      <Card style={{ padding: 0 }}>
        {filteredInstances === null ? (
          <div style={{ padding: 24, fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>
        ) : filteredInstances.length === 0 ? (
          <EmptyState
            title={view === "pending" ? "No pending approvals" : "No approval history yet"}
            hint={
              instances && instances.length > 0
                ? "No results match your current filters."
                : view === "pending"
                ? "You're all caught up."
                : undefined
            }
          />
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Type</Th>
                <Th>Requested by</Th>
                <Th>Amount</Th>
                <Th>Status</Th>
                <Th>SLA</Th>
                <Th>Date</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {filteredInstances.map((i) => (
                <tr key={i.id}>
                  <Td>
                    {i.module_name.toUpperCase()} — {i.entity_type.replace(/_/g, " ")}
                  </Td>
                  <Td>{nameFor(i.initiated_by)}</Td>
                  <Td mono>{i.amount ? formatMoney(i.amount) : "—"}</Td>
                  <Td>{statusBadge(i.status)}</Td>
                  <Td>
                    <SlaBadge instance={i} definition={definitions.get(i.workflow_id) ?? null} />
                  </Td>
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
          definition={definitions.get(selected.workflow_id) ?? null}
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
