import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input, Field, ErrorBanner } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import { usePurchaseRequests, useCreatePurchaseRequest, useSubmitPurchaseRequest, useApprovePurchaseRequest } from "./hooks";

const STATUS_TONE: Record<string, "neutral" | "amber" | "steel" | "green" | "brick"> = {
  draft: "neutral",
  submitted: "steel",
  approved: "green",
  rejected: "brick",
};

export default function PurchaseRequestsPage() {
  const [statusFilter, setStatusFilter] = useState("");
  const { data: prs, isLoading } = usePurchaseRequests(statusFilter || undefined);
  const createPR = useCreatePurchaseRequest();
  const approvePR = useApprovePurchaseRequest();

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ description: "", quantity: "", unit: "", estimated_unit_cost: "" });

  // Per-row submit workflow state: which PR is being submitted, its
  // remaining-budget input, and whether a budget breach requires the
  // explicit override path.
  const [submittingId, setSubmittingId] = useState<string | null>(null);
  const [remainingBudget, setRemainingBudget] = useState("");
  const [breachDetail, setBreachDetail] = useState<string | null>(null);
  const [overrideReason, setOverrideReason] = useState("");
  const submitPR = useSubmitPurchaseRequest(submittingId || undefined);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    await createPR.mutateAsync({
      description: form.description,
      quantity: form.quantity,
      unit: form.unit || undefined,
      estimated_unit_cost: form.estimated_unit_cost || undefined,
    });
    setForm({ description: "", quantity: "", unit: "", estimated_unit_cost: "" });
    setShowForm(false);
  }

  async function handleSubmitAttempt(prId: string) {
    setSubmittingId(prId);
    setBreachDetail(null);
    setOverrideReason("");
  }

  async function handleConfirmSubmit(override: boolean) {
    if (!submittingId) return;
    try {
      await submitPR.mutateAsync({
        remaining_budget: remainingBudget || undefined,
        override,
        override_reason: override ? overrideReason : undefined,
      });
      setSubmittingId(null);
      setBreachDetail(null);
    } catch (err) {
      // The business rule: a budget breach without override comes back
      // as a 409 with the specific figures in `detail` — surface that
      // and offer the override path, rather than a generic failure.
      setBreachDetail(getErrorMessage(err));
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Procurement"
        title="Purchase Requests"
        action={<Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "New request"}</Button>}
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
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </select>
        </Field>
      </div>

      {showForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreate}>
            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr", gap: 16 }}>
              <Field label="Description">
                <Input required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
              </Field>
              <Field label="Quantity">
                <Input required value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
              </Field>
              <Field label="Unit">
                <Input value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} />
              </Field>
              <Field label="Est. unit cost">
                <Input value={form.estimated_unit_cost} onChange={(e) => setForm({ ...form, estimated_unit_cost: e.target.value })} />
              </Field>
            </div>
            <Button type="submit" disabled={createPR.isPending}>
              {createPR.isPending ? "Saving…" : "Save request"}
            </Button>
          </form>
        </Card>
      )}

      {submittingId && (
        <Card style={{ marginBottom: 20 }}>
          <h3 style={{ fontSize: 14, marginBottom: 4 }}>Submit for approval</h3>
          <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
            Enter the CBS line's remaining budget to check this request against it before submitting.
          </p>

          {breachDetail && (
            <ErrorBanner title="This request would breach the remaining CBS budget" detail={breachDetail} />
          )}

          <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 12, marginBottom: breachDetail ? 12 : 0 }}>
            <Field label="Remaining budget (optional)">
              <Input
                placeholder="Leave blank to skip the check"
                value={remainingBudget}
                onChange={(e) => setRemainingBudget(e.target.value)}
              />
            </Field>
            <Button onClick={() => handleConfirmSubmit(false)} disabled={submitPR.isPending} style={{ height: 38, alignSelf: "end" }}>
              {submitPR.isPending ? "Checking…" : "Submit"}
            </Button>
          </div>

          {breachDetail && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 12 }}>
              <Field label="Override justification (required to proceed anyway)">
                <Input required value={overrideReason} onChange={(e) => setOverrideReason(e.target.value)} />
              </Field>
              <Button
                variant="danger"
                onClick={() => handleConfirmSubmit(true)}
                disabled={submitPR.isPending || !overrideReason}
                style={{ height: 38, alignSelf: "end" }}
              >
                Submit with override
              </Button>
            </div>
          )}

          <div style={{ marginTop: 12 }}>
            <button
              onClick={() => setSubmittingId(null)}
              style={{ background: "none", border: "none", color: "var(--sf-navy-400)", fontSize: 12, cursor: "pointer" }}
            >
              Cancel
            </button>
          </div>
        </Card>
      )}

      {isLoading ? (
        <p>Loading…</p>
      ) : !prs?.length ? (
        <EmptyState title="No purchase requests yet" hint="Start a request to have it approved and turned into a purchase order." />
      ) : (
        <Card style={{ padding: 0 }}>
          <Table>
            <thead>
              <tr>
                <Th>Description</Th>
                <Th>Qty</Th>
                <Th>Est. total</Th>
                <Th>Status</Th>
                <Th></Th>
              </tr>
            </thead>
            <tbody>
              {prs.map((pr) => (
                <tr key={pr.id}>
                  <Td>{pr.description}</Td>
                  <Td mono>
                    {pr.quantity} {pr.unit || ""}
                  </Td>
                  <Td mono>{pr.estimated_total || "—"}</Td>
                  <Td>
                    <Badge tone={STATUS_TONE[pr.status] ?? "neutral"}>{pr.status}</Badge>
                    {pr.budget_override && <Badge tone="amber">Override</Badge>}
                  </Td>
                  <Td>
                    {pr.status === "draft" && (
                      <button
                        onClick={() => handleSubmitAttempt(pr.id)}
                        style={{ background: "none", border: "none", color: "var(--sf-steel)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}
                      >
                        Submit
                      </button>
                    )}
                    {pr.status === "submitted" && (
                      <button
                        onClick={() => approvePR.mutate(pr.id)}
                        style={{ background: "none", border: "none", color: "var(--sf-green)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}
                      >
                        Approve
                      </button>
                    )}
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
