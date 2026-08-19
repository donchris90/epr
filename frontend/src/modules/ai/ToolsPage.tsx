import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, Input, Field } from "../../components/ui";
import { useAtRiskProjectsTool, useIdleEquipmentTool, useQueryLogs } from "./hooks";

export default function ToolsPage() {
  const { data: atRisk, refetch: refetchAtRisk, isFetching: fetchingRisk } = useAtRiskProjectsTool("0.9");
  const [period, setPeriod] = useState({ start: "", end: "" });
  const { data: idle, refetch: refetchIdle, isFetching: fetchingIdle } = useIdleEquipmentTool(period.start || undefined, period.end || undefined);
  const { data: logs } = useQueryLogs();

  return (
    <div>
      <PageHeader eyebrow="AI Construction Assistant" title="Grounded Data Tools" />
      <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 20, maxWidth: 640 }}>
        These are the real, structured tools a natural-language layer would call — no LLM is wired in yet (see the
        README), but every call here is grounded in real module data and logged below for auditability.
      </p>

      <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 20 }}>
        <Card>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <h3 style={{ fontSize: 14 }}>At-risk projects (CPI/SPI &lt; 0.9)</h3>
            <Button variant="secondary" onClick={() => refetchAtRisk()} disabled={fetchingRisk}>
              {fetchingRisk ? "Running…" : "Run"}
            </Button>
          </div>
          {atRisk?.length ? (
            <Table>
              <thead><tr><Th>Project</Th><Th>CPI</Th><Th>SPI</Th></tr></thead>
              <tbody>
                {atRisk.map((p: any, i: number) => (
                  <tr key={i}>
                    <Td mono style={{ fontSize: 11 }}>{p.project_id.slice(0, 8)}…</Td>
                    <Td><Badge tone="brick">{p.cpi}</Badge></Td>
                    <Td><Badge tone="brick">{p.spi}</Badge></Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <p style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>No at-risk projects found.</p>
          )}
        </Card>

        <Card>
          <h3 style={{ fontSize: 14, marginBottom: 12 }}>Idle equipment</h3>
          <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: 8, marginBottom: 12 }}>
            <Field label="Period start">
              <Input type="date" value={period.start} onChange={(e) => setPeriod({ ...period, start: e.target.value })} />
            </Field>
            <Field label="Period end">
              <Input type="date" value={period.end} onChange={(e) => setPeriod({ ...period, end: e.target.value })} />
            </Field>
            <Button variant="secondary" onClick={() => refetchIdle()} disabled={fetchingIdle || !period.start || !period.end} style={{ height: 38, alignSelf: "end" }}>
              Run
            </Button>
          </div>
          {idle?.length ? (
            <ul style={{ margin: 0, padding: 0, listStyle: "none", fontSize: 13 }}>
              {idle.map((e: any) => (
                <li key={e.equipment_id} style={{ padding: "4px 0" }}>{e.name}</li>
              ))}
            </ul>
          ) : (
            <p style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>Select a period and run to check.</p>
          )}
        </Card>
      </div>

      <Card>
        <h3 style={{ fontSize: 14, marginBottom: 12 }}>Query audit log</h3>
        {logs?.length ? (
          <Table>
            <thead><tr><Th>Tool</Th><Th>When</Th></tr></thead>
            <tbody>
              {logs.map((l: any) => (
                <tr key={l.id}>
                  <Td mono>{l.tool_name}</Td>
                  <Td mono>{l.queried_at ? new Date(l.queried_at).toLocaleString() : "—"}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        ) : (
          <p style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>No tool calls logged yet — run a tool above.</p>
        )}
      </Card>
    </div>
  );
}
