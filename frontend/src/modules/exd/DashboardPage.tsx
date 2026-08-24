import { PageHeader, Card, Table, Th, Td, Badge, EmptyState } from "../../components/ui";
import { useCompanyRevenue, useActiveProjectsPerformance, useProjectRisks, useARAPAging, useEquipmentUtilization } from "./hooks";

export default function DashboardPage() {
  const { data: revenue } = useCompanyRevenue();
  const { data: performance } = useActiveProjectsPerformance();
  const { data: risks } = useProjectRisks();
  const { data: aging } = useARAPAging();
  const { data: utilization } = useEquipmentUtilization();

  return (
    <div>
      <PageHeader eyebrow="Executive Dashboard" title="Company Overview" />

      <div className="row g-3 mb-3">
        <div className="col-12 col-md-6 col-lg-4">
        <Card>
          <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase", marginBottom: 8 }}>Revenue (actual vs budget)</div>
          {revenue ? (
            <div>
              <div className="sf-mono" style={{ fontSize: 22, fontWeight: 700 }}>{revenue.actual_revenue}</div>
              <div style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>Budget: <span className="sf-mono">{revenue.budgeted_revenue}</span></div>
              <Badge tone={Number(revenue.variance) >= 0 ? "green" : "brick"}>
                {revenue.variance_pct}% {Number(revenue.variance) >= 0 ? "above" : "below"} budget
              </Badge>
            </div>
          ) : (
            <EmptyState compact title="No revenue data yet." />
          )}
        </Card>
        </div>

        <div className="col-12 col-md-6 col-lg-4">
        <Card>
          <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase", marginBottom: 8 }}>AR / AP Aging</div>
          {aging ? (
            <div style={{ fontSize: 13, display: "grid", gap: 4 }}>
              <div>Receivable: <span className="sf-mono">{aging.total_receivable ?? "—"}</span></div>
              <div>Payable: <span className="sf-mono">{aging.total_payable ?? "—"}</span></div>
            </div>
          ) : (
            <EmptyState compact title="No aging data yet." />
          )}
        </Card>
        </div>

        <div className="col-12 col-md-6 col-lg-4">
        <Card>
          <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase", marginBottom: 8 }}>Equipment Utilization</div>
          {utilization?.length ? (
            <div style={{ fontSize: 13, display: "grid", gap: 4 }}>
              {utilization.map((u: any, i: number) => (
                <div key={i}>
                  {u.ownership_type}: <span className="sf-mono">{u.utilization_pct}%</span>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState compact title="No utilization data yet." />
          )}
        </Card>
        </div>
      </div>

      <div className="row g-3">
        <div className="col-12 col-lg-6">
        <Card style={{ padding: 0 }}>
          <div style={{ padding: "12px 16px 0" }}>
            <h3 style={{ fontSize: 14, marginBottom: 12 }}>Active projects — CPI / SPI</h3>
          </div>
          {performance?.length ? (
            <Table>
              <thead><tr><Th>Project</Th><Th>CPI</Th><Th>SPI</Th></tr></thead>
              <tbody>
                {performance.map((p: any) => (
                  <tr key={p.project_id}>
                    <Td mono style={{ fontSize: 11 }}>{p.project_id.slice(0, 8)}…</Td>
                    <Td><Badge tone={Number(p.cpi) < 0.9 ? "brick" : "green"}>{p.cpi ?? "—"}</Badge></Td>
                    <Td><Badge tone={Number(p.spi) < 0.9 ? "brick" : "green"}>{p.spi ?? "—"}</Badge></Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <p style={{ fontSize: 12, color: "var(--sf-navy-400)", padding: 16 }}>No active project data yet.</p>
          )}
        </Card>
        </div>

        <div className="col-12 col-lg-6">
        <Card style={{ padding: 0 }}>
          <div style={{ padding: "12px 16px 0" }}>
            <h3 style={{ fontSize: 14, marginBottom: 12 }}>Consolidated project risks</h3>
          </div>
          {risks?.length ? (
            <Table>
              <thead><tr><Th>Description</Th><Th>Exposure</Th></tr></thead>
              <tbody>
                {risks.map((r: any) => (
                  <tr key={r.id}>
                    <Td>{r.description}</Td>
                    <Td mono>{r.exposure_value}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <p style={{ fontSize: 12, color: "var(--sf-navy-400)", padding: 16 }}>No open risks across active projects.</p>
          )}
        </Card>
        </div>
      </div>
    </div>
  );
}
