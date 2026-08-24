import { useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader, Card, Button, Table, Th, Td, Badge, Input, Field, EmptyState, formatMoney } from "../../components/ui";
import { useGeneratePayrollRun, usePayrollRuns } from "./hooks";

/** Real payroll history -- lists every real payroll run (GET
 * /v1/wfm/payroll-runs, added this batch), each linking to its own
 * real PayrollRunDetailPage for review/payslips/bank export/finance
 * posting/finalize. */
export default function PayrollPage() {
  const { data: runs, isLoading } = usePayrollRuns();
  const generateRun = useGeneratePayrollRun();
  const [form, setForm] = useState({ period_start: "", period_end: "" });
  const [showForm, setShowForm] = useState(false);

  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault();
    await generateRun.mutateAsync(form);
    setForm({ period_start: "", period_end: "" });
    setShowForm(false);
  }

  return (
    <div>
      <PageHeader
        eyebrow="Workforce Management"
        title="Payroll History"
        action={<Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "Generate payroll run"}</Button>}
      />

      {showForm && (
        <Card style={{ marginBottom: 20 }}>
          <h3 style={{ fontSize: 14, marginBottom: 12 }}>Generate a payroll run</h3>
          <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
            Only approved or locked timesheets for this period will be included.
          </p>
          <form onSubmit={handleGenerate} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: 12 }}>
            <Field label="Period start">
              <Input required type="date" value={form.period_start} onChange={(e) => setForm({ ...form, period_start: e.target.value })} />
            </Field>
            <Field label="Period end">
              <Input required type="date" value={form.period_end} onChange={(e) => setForm({ ...form, period_end: e.target.value })} />
            </Field>
            <Button type="submit" disabled={generateRun.isPending} style={{ height: 38, alignSelf: "end" }}>
              {generateRun.isPending ? "Generating…" : "Generate"}
            </Button>
          </form>
        </Card>
      )}

      {isLoading ? (
        <div style={{ padding: 32, fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>
      ) : !runs?.length ? (
        <EmptyState title="No payroll runs yet." hint="Generate one from approved or locked timesheets to get started." />
      ) : (
        <Card style={{ padding: 0 }}>
          <Table>
            <thead><tr><Th>Period</Th><Th>Gross</Th><Th>Net</Th><Th>Status</Th></tr></thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id}>
                  <Td><Link to={`/workforce/payroll/${run.id}`}>{run.period_start} → {run.period_end}</Link></Td>
                  <Td mono>{formatMoney(run.total_gross)}</Td>
                  <Td mono>{formatMoney(run.total_net)}</Td>
                  <Td><Badge tone={run.status === "finalized" ? "green" : "amber"}>{run.status}</Badge></Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
    </div>
  );
}
