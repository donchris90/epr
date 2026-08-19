import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input, Field } from "../../components/ui";
import { ProjectSelect } from "../../components/ProjectSelect";
import { useEVMSnapshots, useCreateEVMSnapshot, useAtRiskProjects, useGenerateForecast, useRiskRegister, useCreateRiskEntry } from "./hooks";

export default function EVMPage() {
  const [projectId, setProjectId] = useState("");
  const { data: snapshots, isLoading } = useEVMSnapshots(projectId || undefined);
  const createSnapshot = useCreateEVMSnapshot();
  const generateForecast = useGenerateForecast();
  const [forecastResult, setForecastResult] = useState<any>(null);

  const { data: atRisk } = useAtRiskProjects("0.9");

  const { data: risks } = useRiskRegister(projectId || undefined);
  const createRisk = useCreateRiskEntry();
  const [riskForm, setRiskForm] = useState({ description: "", probability: "", impact_value: "" });
  const [showRiskForm, setShowRiskForm] = useState(false);

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ period_end: "", planned_value: "", earned_value: "", actual_cost: "", budget_at_completion: "" });

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    await createSnapshot.mutateAsync({ project_id: projectId, ...form });
    setForm({ period_end: "", planned_value: "", earned_value: "", actual_cost: "", budget_at_completion: "" });
    setShowForm(false);
  }

  async function handleForecast(snapshotId: string) {
    const res = await generateForecast.mutateAsync({ snapshotId });
    setForecastResult(res.data);
  }

  async function handleAddRisk(e: React.FormEvent) {
    e.preventDefault();
    await createRisk.mutateAsync({ project_id: projectId, ...riskForm });
    setRiskForm({ description: "", probability: "", impact_value: "" });
    setShowRiskForm(false);
  }

  return (
    <div>
      <PageHeader
        eyebrow="Project Controls"
        title="Earned Value Management"
        action={<Button onClick={() => setShowForm((v) => !v)} disabled={!projectId}>{showForm ? "Cancel" : "New snapshot"}</Button>}
      />

      {atRisk?.length ? (
        <Card style={{ marginBottom: 20, borderColor: "var(--sf-brick)" }}>
          <div style={{ fontSize: 13, color: "var(--sf-brick)", fontWeight: 600 }}>
            {atRisk.length} project(s) at risk (CPI or SPI below threshold)
          </div>
        </Card>
      ) : null}

      <div style={{ marginBottom: 20, maxWidth: 320 }}>
        <Field label="Project ID">
          <ProjectSelect value={projectId} onChange={setProjectId} />
        </Field>
      </div>

      {showForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreate} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr 1fr auto", gap: 8 }}>
            <Input required type="date" value={form.period_end} onChange={(e) => setForm({ ...form, period_end: e.target.value })} />
            <Input required placeholder="PV" value={form.planned_value} onChange={(e) => setForm({ ...form, planned_value: e.target.value })} />
            <Input required placeholder="EV" value={form.earned_value} onChange={(e) => setForm({ ...form, earned_value: e.target.value })} />
            <Input required placeholder="AC" value={form.actual_cost} onChange={(e) => setForm({ ...form, actual_cost: e.target.value })} />
            <Input required placeholder="BAC" value={form.budget_at_completion} onChange={(e) => setForm({ ...form, budget_at_completion: e.target.value })} />
            <Button type="submit" disabled={createSnapshot.isPending}>Add</Button>
          </form>
        </Card>
      )}

      {forecastResult && (
        <Card style={{ marginBottom: 20 }}>
          <h3 style={{ fontSize: 14, marginBottom: 8 }}>Forecast ({forecastResult.method})</h3>
          <div style={{ display: "flex", gap: 32, fontSize: 13 }}>
            <div><span style={{ color: "var(--sf-navy-400)" }}>EAC: </span><span className="sf-mono" style={{ fontWeight: 700 }}>{forecastResult.estimate_at_completion}</span></div>
            <div><span style={{ color: "var(--sf-navy-400)" }}>ETC: </span><span className="sf-mono">{forecastResult.estimate_to_complete}</span></div>
            <div><span style={{ color: "var(--sf-navy-400)" }}>VAC: </span><span className="sf-mono">{forecastResult.variance_at_completion}</span></div>
          </div>
        </Card>
      )}

      {!projectId ? (
        <EmptyState title="Enter a project ID" hint="EVM snapshots are tracked per project." />
      ) : isLoading ? (
        <p>Loading…</p>
      ) : !snapshots?.length ? (
        <EmptyState title="No EVM snapshots yet" hint="Add a snapshot with PV/EV/AC/BAC to compute CPI, SPI, and variances." />
      ) : (
        <Card style={{ padding: 0, marginBottom: 20 }}>
          <Table>
            <thead><tr><Th>Period</Th><Th>CPI</Th><Th>SPI</Th><Th>CV</Th><Th>SV</Th><Th></Th></tr></thead>
            <tbody>
              {snapshots.map((s: any) => (
                <tr key={s.id}>
                  <Td mono>{s.period_end}</Td>
                  <Td><Badge tone={Number(s.cpi) < 0.9 ? "brick" : "green"}>{s.cpi ?? "—"}</Badge></Td>
                  <Td><Badge tone={Number(s.spi) < 0.9 ? "brick" : "green"}>{s.spi ?? "—"}</Badge></Td>
                  <Td mono>{s.cost_variance}</Td>
                  <Td mono>{s.schedule_variance}</Td>
                  <Td>
                    <button onClick={() => handleForecast(s.id)} style={{ background: "none", border: "none", color: "var(--sf-steel)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
                      Forecast
                    </button>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}

      {projectId && (
        <Card>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <h3 style={{ fontSize: 14 }}>Risk register</h3>
            <Button variant="secondary" onClick={() => setShowRiskForm((v) => !v)}>{showRiskForm ? "Cancel" : "New risk"}</Button>
          </div>
          {showRiskForm && (
            <form onSubmit={handleAddRisk} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr auto", gap: 8, marginBottom: 12 }}>
              <Input required placeholder="Description" value={riskForm.description} onChange={(e) => setRiskForm({ ...riskForm, description: e.target.value })} />
              <Input required placeholder="Probability (0-1)" value={riskForm.probability} onChange={(e) => setRiskForm({ ...riskForm, probability: e.target.value })} />
              <Input required placeholder="Impact value" value={riskForm.impact_value} onChange={(e) => setRiskForm({ ...riskForm, impact_value: e.target.value })} />
              <Button type="submit" disabled={createRisk.isPending}>Add</Button>
            </form>
          )}
          {risks?.length ? (
            <Table>
              <thead><tr><Th>Description</Th><Th>Exposure</Th><Th>Status</Th></tr></thead>
              <tbody>
                {risks.map((r: any) => (
                  <tr key={r.id}>
                    <Td>{r.description}</Td>
                    <Td mono>{r.exposure_value}</Td>
                    <Td><Badge tone="neutral">{r.status}</Badge></Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <p style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>No risks logged for this project.</p>
          )}
        </Card>
      )}
    </div>
  );
}
