import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, Input, Field } from "../../components/ui";
import { useGeneratePayrollRun, usePayrollRun, useFinalizePayrollRun } from "./hooks";

export default function PayrollPage() {
  const generateRun = useGeneratePayrollRun();
  const finalizeRun = useFinalizePayrollRun();
  const [form, setForm] = useState({ period_start: "", period_end: "" });
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const { data: run } = usePayrollRun(currentRunId || undefined);

  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault();
    const res = await generateRun.mutateAsync(form);
    setCurrentRunId(res.data.id);
  }

  return (
    <div>
      <PageHeader eyebrow="Workforce Management" title="Payroll" />

      <Card style={{ marginBottom: 20 }}>
        <h3 style={{ fontSize: 14, marginBottom: 12 }}>Generate a payroll run</h3>
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

      {run && (
        <Card>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <h3 style={{ fontSize: 14 }}>Run: {run.period_start} → {run.period_end}</h3>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <Badge tone={run.status === "finalized" ? "green" : "amber"}>{run.status}</Badge>
              {run.status !== "finalized" && (
                <Button disabled={finalizeRun.isPending} onClick={() => finalizeRun.mutate(run.id)}>
                  {finalizeRun.isPending ? "Finalizing…" : "Finalize"}
                </Button>
              )}
            </div>
          </div>
          {run.lines?.length ? (
            <Table>
              <thead><tr><Th>Employee/Worker</Th><Th>Gross</Th><Th>Net</Th></tr></thead>
              <tbody>
                {run.lines.map((line: any) => (
                  <tr key={line.id}>
                    <Td mono style={{ fontSize: 11 }}>{(line.employee_id || line.casual_worker_id || "").slice(0, 8)}…</Td>
                    <Td mono>{line.gross_amount}</Td>
                    <Td mono>{line.net_amount}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <p style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>No lines in this run.</p>
          )}
        </Card>
      )}
    </div>
  );
}
