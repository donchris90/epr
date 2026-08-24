import { PageHeader, Card, Table, Th, Td, Badge, EmptyState, formatMoney } from "../../components/ui";
import {
  useCompanyRevenue,
  useActiveProjectsPerformance,
  useProjectRisks,
  useARAPAging,
  useEquipmentUtilization,
  useProjectNames,
  useIncidents,
  sumAgingBands,
} from "./hooks";
import { useTenders } from "../tbm/hooks";
import { useEmployees } from "../wfm/hooks";
import type { TenderStatus } from "../tbm/types";

const TENDER_STATUS_LABEL: Record<TenderStatus, string> = {
  draft: "Draft",
  in_estimate: "In estimate",
  in_approval: "In approval",
  submitted: "Submitted",
  awarded: "Awarded",
  lost: "Lost",
};

const CLASSIFICATION_LABEL: Record<string, string> = {
  first_aid: "First aid",
  medical_treatment: "Medical treatment",
  lost_time: "Lost time",
  fatality: "Fatality",
};

function sectionHeading(text: string) {
  return <h2 style={{ fontSize: 15, fontWeight: 700, color: "var(--sf-navy-900)", margin: "28px 0 12px" }}>{text}</h2>;
}

function metricLabel(text: string) {
  return <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase", marginBottom: 8 }}>{text}</div>;
}

/** Real executive dashboard, organized into Financial / Projects /
 * Commercial / HSE / Workforce, using only real backend data --
 * every figure here traces to a real endpoint, checked directly
 * before building this. See docs/EXECUTIVE_DASHBOARD_GAPS.md for
 * what's genuinely not backed (margin, cash, on-track/delayed/over-
 * budget project classification, productivity) and why.
 *
 * Two real, previously-hidden bugs found and fixed while building
 * this: company-revenue and equipment-utilization both require real
 * period_start/period_end query params the dashboard never sent,
 * meaning both widgets have always failed silently (see hooks.ts's
 * own docstring); and this page itself read a nonexistent
 * `budgeted_revenue` field (the real one is `budget_amount`) and
 * showed a raw, truncated project UUID instead of a name. */
export default function DashboardPage() {
  const { data: revenue } = useCompanyRevenue();
  const { data: performance } = useActiveProjectsPerformance();
  const { data: risks } = useProjectRisks();
  const { data: aging } = useARAPAging();
  const { data: utilization } = useEquipmentUtilization();
  const { data: projectNames } = useProjectNames();
  const { data: tenders } = useTenders();
  const { data: incidents } = useIncidents();
  const { data: employees } = useEmployees();

  const projectNameById = new Map((projectNames ?? []).map((p) => [p.id, p.name]));

  const tenderCounts = (tenders ?? []).reduce<Record<string, number>>((acc, t) => {
    acc[t.status] = (acc[t.status] ?? 0) + 1;
    return acc;
  }, {});
  const awarded = tenderCounts.awarded ?? 0;
  const lost = tenderCounts.lost ?? 0;
  const winRate = awarded + lost > 0 ? Math.round((awarded / (awarded + lost)) * 100) : null;

  const incidentsByClassification = (incidents ?? []).reduce<Record<string, number>>((acc, i) => {
    acc[i.classification] = (acc[i.classification] ?? 0) + 1;
    return acc;
  }, {});
  // Real trend: incidents grouped by month, using occurred_at (a
  // real, already-existing model field, exposed on the schema
  // specifically for this -- see backend/app/modules/hse/schemas.py).
  const incidentsByMonth = (incidents ?? [])
    .filter((i) => i.occurred_at)
    .reduce<Record<string, number>>((acc, i) => {
      const month = i.occurred_at!.slice(0, 7);
      acc[month] = (acc[month] ?? 0) + 1;
      return acc;
    }, {});
  const sortedMonths = Object.keys(incidentsByMonth).sort().slice(-6);

  const activeEmployees = (employees ?? []).filter((e) => e.status === "active");
  const permanentCount = activeEmployees.filter((e) => e.employment_type === "permanent").length;
  const contractCount = activeEmployees.filter((e) => e.employment_type === "contract").length;

  return (
    <div>
      <PageHeader eyebrow="Executive Dashboard" title="Company Overview" />

      {sectionHeading("Financial")}
      <div className="row g-3">
        <div className="col-12 col-md-6 col-lg-4">
          <Card>
            {metricLabel("Revenue (actual vs budget), year to date")}
            {revenue ? (
              <div>
                <div className="sf-mono" style={{ fontSize: 22, fontWeight: 700 }}>{formatMoney(revenue.actual_revenue)}</div>
                <div style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>
                  Budget: <span className="sf-mono">{revenue.budget_amount ? formatMoney(revenue.budget_amount) : "Not set"}</span>
                </div>
                {revenue.variance_pct != null && (
                  <Badge tone={Number(revenue.variance) >= 0 ? "green" : "brick"}>
                    {revenue.variance_pct}% {Number(revenue.variance) >= 0 ? "above" : "below"} budget
                  </Badge>
                )}
              </div>
            ) : (
              <EmptyState compact title="No revenue data yet." />
            )}
          </Card>
        </div>

        <div className="col-12 col-md-6 col-lg-4">
          <Card>
            {metricLabel("Receivables / Payables")}
            {aging ? (
              <div style={{ fontSize: 13, display: "grid", gap: 4 }}>
                <div>Receivable: <span className="sf-mono">{formatMoney(sumAgingBands(aging.accounts_receivable))}</span></div>
                <div>Payable: <span className="sf-mono">{formatMoney(sumAgingBands(aging.accounts_payable))}</span></div>
              </div>
            ) : (
              <EmptyState compact title="No aging data yet." />
            )}
          </Card>
        </div>

        <div className="col-12 col-md-6 col-lg-4">
          <Card>
            {metricLabel("Equipment Utilization, year to date")}
            {utilization?.length ? (
              <div style={{ fontSize: 13, display: "grid", gap: 4 }}>
                {utilization.map((u) => (
                  <div key={u.ownership_type}>
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

      {sectionHeading("Projects")}
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
                  {performance.map((p) => (
                    <tr key={p.project_id}>
                      <Td>{projectNameById.get(p.project_id) ?? "Unknown project"}</Td>
                      <Td><Badge tone={p.cpi != null && Number(p.cpi) < 0.9 ? "brick" : "green"}>{p.cpi ?? "—"}</Badge></Td>
                      <Td><Badge tone={p.spi != null && Number(p.spi) < 0.9 ? "brick" : "green"}>{p.spi ?? "—"}</Badge></Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            ) : (
              <EmptyState compact title="No active project data yet." />
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
                  {risks.map((r) => (
                    <tr key={r.id}>
                      <Td>{r.description}</Td>
                      <Td mono>{formatMoney(r.exposure_value)}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            ) : (
              <EmptyState compact title="No open risks across active projects." />
            )}
          </Card>
        </div>
      </div>

      {sectionHeading("Commercial")}
      <div className="row g-3">
        <div className="col-12 col-lg-8">
          <Card>
            {metricLabel("Tender pipeline")}
            {tenders?.length ? (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 16 }}>
                {(Object.keys(TENDER_STATUS_LABEL) as TenderStatus[]).map((status) =>
                  tenderCounts[status] ? (
                    <div key={status}>
                      <div className="sf-mono" style={{ fontSize: 20, fontWeight: 700 }}>{tenderCounts[status]}</div>
                      <div style={{ fontSize: 11, color: "var(--sf-navy-400)" }}>{TENDER_STATUS_LABEL[status]}</div>
                    </div>
                  ) : null
                )}
              </div>
            ) : (
              <EmptyState compact title="No tenders yet." />
            )}
          </Card>
        </div>
        <div className="col-12 col-lg-4">
          <Card>
            {metricLabel("Win rate (awarded vs lost)")}
            {winRate != null ? (
              <div className="sf-mono" style={{ fontSize: 22, fontWeight: 700 }}>{winRate}%</div>
            ) : (
              <EmptyState compact title="Not enough decided tenders yet." />
            )}
          </Card>
        </div>
      </div>

      {sectionHeading("HSE")}
      <div className="row g-3">
        <div className="col-12 col-lg-6">
          <Card>
            {metricLabel("Incidents by classification")}
            {incidents?.length ? (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 16 }}>
                {Object.entries(incidentsByClassification).map(([classification, count]) => (
                  <div key={classification}>
                    <div className="sf-mono" style={{ fontSize: 20, fontWeight: 700, color: classification === "fatality" || classification === "lost_time" ? "var(--sf-brick)" : "inherit" }}>
                      {count}
                    </div>
                    <div style={{ fontSize: 11, color: "var(--sf-navy-400)" }}>{CLASSIFICATION_LABEL[classification] ?? classification}</div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState compact title="No incidents recorded." />
            )}
          </Card>
        </div>
        <div className="col-12 col-lg-6">
          <Card>
            {metricLabel("Safety trend, last 6 months with data")}
            {sortedMonths.length ? (
              <div style={{ fontSize: 13, display: "grid", gap: 4 }}>
                {sortedMonths.map((month) => (
                  <div key={month} style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>{month}</span>
                    <span className="sf-mono">{incidentsByMonth[month]}</span>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState compact title="Not enough dated incidents to show a trend." />
            )}
          </Card>
        </div>
      </div>

      {sectionHeading("Workforce")}
      <div className="row g-3">
        <div className="col-12 col-lg-4">
          <Card>
            {metricLabel("Active headcount")}
            {employees?.length ? (
              <div className="sf-mono" style={{ fontSize: 22, fontWeight: 700 }}>{activeEmployees.length}</div>
            ) : (
              <EmptyState compact title="No employees recorded yet." />
            )}
          </Card>
        </div>
        <div className="col-12 col-lg-8">
          <Card>
            {metricLabel("By employment type")}
            {employees?.length ? (
              <div style={{ display: "flex", gap: 16 }}>
                <div>
                  <div className="sf-mono" style={{ fontSize: 20, fontWeight: 700 }}>{permanentCount}</div>
                  <div style={{ fontSize: 11, color: "var(--sf-navy-400)" }}>Permanent</div>
                </div>
                <div>
                  <div className="sf-mono" style={{ fontSize: 20, fontWeight: 700 }}>{contractCount}</div>
                  <div style={{ fontSize: 11, color: "var(--sf-navy-400)" }}>Contract</div>
                </div>
              </div>
            ) : (
              <EmptyState compact title="No employees recorded yet." />
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
