import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Input, Field, ErrorBanner } from "../../components/ui";
import { ProjectSelect } from "../../components/ProjectSelect";
import { getErrorMessage } from "../../api/client";
import { useGenerateIncomeStatement, useProjectCostSummary, useCheckBudgetControl } from "./hooks";

export default function ReportsPage() {
  return (
    <div>
      <PageHeader eyebrow="Financial Management" title="Reports" />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 20 }}>
        <IncomeStatementCard />
        <BudgetControlCheckCard />
      </div>
      <ProjectCostSummaryCard />
    </div>
  );
}

function IncomeStatementCard() {
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const generate = useGenerateIncomeStatement();
  const [error, setError] = useState<string | null>(null);

  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await generate.mutateAsync({ period_start: periodStart, period_end: periodEnd });
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <Card>
      <h3 style={{ fontSize: 14, marginBottom: 12 }}>Income statement</h3>
      {error && <ErrorBanner title="Could not generate" detail={error} onDismiss={() => setError(null)} />}
      <form onSubmit={handleGenerate} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
        <Field label="Period start">
          <Input required type="date" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} />
        </Field>
        <Field label="Period end">
          <Input required type="date" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} />
        </Field>
      </form>
      <Button onClick={handleGenerate} disabled={generate.isPending}>
        {generate.isPending ? "Generating…" : "Generate"}
      </Button>

      {generate.data && (
        <div style={{ marginTop: 16, fontSize: 13, display: "grid", gap: 6 }}>
          {Object.entries(generate.data.data.data || {}).map(([key, value]) => (
            <div key={key} style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ textTransform: "capitalize" }}>{key.replace(/_/g, " ")}</span>
              <span className="sf-mono">{value as string}</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function BudgetControlCheckCard() {
  const [form, setForm] = useState({ cost_code: "", posting_amount: "", cbs_budget_amount: "", cost_category: "" });
  const check = useCheckBudgetControl();
  const [error, setError] = useState<string | null>(null);

  async function handleCheck(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await check.mutateAsync({ ...form, cost_category: form.cost_category || undefined });
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <Card>
      <h3 style={{ fontSize: 14, marginBottom: 4 }}>Budget control check</h3>
      <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
        Checks a posting against a CBS cost code's remaining budget — enforcement (hard block vs. warning) follows
        whatever policy applies to the cost category.
      </p>
      {error && <ErrorBanner title="Blocked by budget policy" detail={error} onDismiss={() => setError(null)} />}
      <form onSubmit={handleCheck} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
        <Field label="Cost code (CBS line UUID)">
          <Input required value={form.cost_code} onChange={(e) => setForm({ ...form, cost_code: e.target.value })} />
        </Field>
        <Field label="Cost category (optional)">
          <Input value={form.cost_category} onChange={(e) => setForm({ ...form, cost_category: e.target.value })} />
        </Field>
        <Field label="Posting amount">
          <Input required value={form.posting_amount} onChange={(e) => setForm({ ...form, posting_amount: e.target.value })} />
        </Field>
        <Field label="CBS budget amount">
          <Input required value={form.cbs_budget_amount} onChange={(e) => setForm({ ...form, cbs_budget_amount: e.target.value })} />
        </Field>
      </form>
      <Button onClick={handleCheck} disabled={check.isPending}>
        {check.isPending ? "Checking…" : "Check"}
      </Button>

      {check.data && (
        <div style={{ marginTop: 16, fontSize: 13 }}>
          <div>
            Allowed: <strong>{String(check.data.data.allowed)}</strong>
          </div>
          <div>
            Warning: <strong>{String(check.data.data.warning)}</strong>
          </div>
          <div className="sf-mono">Remaining before this posting: {check.data.data.remaining_before}</div>
        </div>
      )}
    </Card>
  );
}

function ProjectCostSummaryCard() {
  const [projectId, setProjectId] = useState("");
  const { data: summary, isLoading } = useProjectCostSummary(projectId || undefined);

  return (
    <Card>
      <h3 style={{ fontSize: 14, marginBottom: 12 }}>Project cost summary</h3>
      <div style={{ maxWidth: 320, marginBottom: 16 }}>
        <Field label="Project ID">
          <ProjectSelect value={projectId} onChange={setProjectId} />
        </Field>
      </div>
      {isLoading ? (
        <p>Loading…</p>
      ) : summary?.length ? (
        <Table>
          <thead>
            <tr>
              <Th>Cost code</Th>
              <Th>Net amount</Th>
            </tr>
          </thead>
          <tbody>
            {summary.map((row: any, i: number) => (
              <tr key={i}>
                <Td mono>{row.cost_code ?? "Unallocated"}</Td>
                <Td mono>{row.net_amount}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      ) : (
        projectId && <p style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>No posted costs found for this project.</p>
      )}
    </Card>
  );
}
