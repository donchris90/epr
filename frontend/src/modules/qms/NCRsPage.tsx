import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input, Field, ErrorBanner } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import { useNCRs, useCreateNCR, useDispositionNCR, useCloseNCR, useCreateCorrectiveAction, type NCR } from "./hooks";

const STATUS_TONE: Record<string, "neutral" | "amber" | "steel" | "green" | "brick"> = {
  open: "amber",
  dispositioned: "steel",
  closed: "green",
};

export default function NCRsPage() {
  const { data: ncrs, isLoading } = useNCRs();
  const createNCR = useCreateNCR();
  const dispositionNCR = useDispositionNCR();
  const closeNCR = useCloseNCR();
  const createAction = useCreateCorrectiveAction();

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ description: "", root_cause: "" });
  const [closeError, setCloseError] = useState<string | null>(null);
  const [actionDesc, setActionDesc] = useState<Record<string, string>>({});

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    await createNCR.mutateAsync(form);
    setForm({ description: "", root_cause: "" });
    setShowForm(false);
  }

  async function handleClose(ncrId: string) {
    setCloseError(null);
    try {
      await closeNCR.mutateAsync(ncrId);
    } catch (err) {
      // Business rule: a linked corrective action must be VERIFIED,
      // not just completed, before the NCR can close.
      setCloseError(getErrorMessage(err));
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Quality Management"
        title="Non-Conformance Reports"
        action={<Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "New NCR"}</Button>}
      />

      {closeError && <ErrorBanner title="Cannot close" detail={closeError} onDismiss={() => setCloseError(null)} />}

      {showForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreate}>
            <Field label="Description">
              <Input required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </Field>
            <Field label="Root cause (optional)">
              <Input value={form.root_cause} onChange={(e) => setForm({ ...form, root_cause: e.target.value })} />
            </Field>
            <Button type="submit" disabled={createNCR.isPending}>{createNCR.isPending ? "Saving…" : "Log NCR"}</Button>
          </form>
        </Card>
      )}

      {isLoading ? (
        <p>Loading…</p>
      ) : !ncrs?.length ? (
        <EmptyState title="No NCRs logged" hint="Quality issues raised on site appear here for disposition and closure." />
      ) : (
        <Card style={{ padding: 0 }}>
          <Table>
            <thead><tr><Th>Description</Th><Th>Disposition</Th><Th>Status</Th><Th>Actions</Th></tr></thead>
            <tbody>
              {ncrs.map((n: NCR) => (
                <tr key={n.id}>
                  <Td>{n.description}</Td>
                  <Td>{n.disposition || "—"}</Td>
                  <Td><Badge tone={STATUS_TONE[n.status] ?? "neutral"}>{n.status}</Badge></Td>
                  <Td>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                      {n.status === "open" && (
                        <select
                          onChange={(e) => e.target.value && dispositionNCR.mutate({ ncrId: n.id, disposition: e.target.value })}
                          style={{ fontSize: 11, padding: "4px 6px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)" }}
                          defaultValue=""
                        >
                          <option value="" disabled>Disposition…</option>
                          <option value="accept_as_is">Accept as is</option>
                          <option value="rework">Rework</option>
                          <option value="reject">Reject</option>
                        </select>
                      )}
                      {n.status !== "closed" && (
                        <>
                          <Input
                            placeholder="Corrective action"
                            value={actionDesc[n.id] || ""}
                            onChange={(e) => setActionDesc({ ...actionDesc, [n.id]: e.target.value })}
                            style={{ width: 140, fontSize: 11 }}
                          />
                          <button
                            disabled={!actionDesc[n.id]}
                            onClick={() => createAction.mutate({ source: "ncr", ncr_id: n.id, description: actionDesc[n.id] })}
                            style={{ background: "none", border: "none", color: "var(--sf-steel)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}
                          >
                            Log action
                          </button>
                          <button onClick={() => handleClose(n.id)} style={{ background: "none", border: "none", color: "var(--sf-green)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
                            Close
                          </button>
                        </>
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
