import { Card, Badge } from "../../components/ui";
import {
  useActiveProjectsPerformance,
  useProjectNames,
  useContractsForAlerts,
  useARAPAging,
  useIncidents,
  usePendingApprovalsForAlerts,
  useWorkflowDefinitionsForAlerts,
} from "./hooks";
import { computeExecutiveAlerts, ALERT_TYPE_LABEL, type ExecutiveAlert } from "./alerts";

function AlertRow({ alert }: { alert: ExecutiveAlert }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "10px 0", borderBottom: "1px solid var(--sf-line)" }}>
      <Badge tone={alert.severity === "high" ? "brick" : "amber"}>{ALERT_TYPE_LABEL[alert.type]}</Badge>
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--sf-navy-900)" }}>{alert.title}</div>
        <div style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>{alert.detail}</div>
      </div>
    </div>
  );
}

/** Real Executive Alerts, computed entirely from data already
 * verified to exist -- see alerts.ts's own docstring for the exact
 * reasoning behind each alert type, and
 * docs/EXECUTIVE_DASHBOARD_GAPS.md for what's genuinely not alerted
 * on. Every real fetch here is independent (a permission denial or
 * failure on one, e.g. approval-overdue's own workflow:approve
 * requirement, doesn't blank the others -- each hook's data is
 * simply undefined and computeExecutiveAlerts treats that source as
 * "nothing to alert on yet," not an error for the whole panel). No
 * alert type is ever shown as a static, unconditional list -- every
 * row here traces back to a real row of real data. */
export default function ExecutiveAlerts() {
  const { data: performance } = useActiveProjectsPerformance();
  const { data: projectNames } = useProjectNames();
  const { data: contracts } = useContractsForAlerts();
  const { data: aging } = useARAPAging();
  const { data: incidents } = useIncidents();
  const { data: pendingApprovals } = usePendingApprovalsForAlerts();
  const { data: workflowDefinitions } = useWorkflowDefinitionsForAlerts();

  const alerts = computeExecutiveAlerts({
    performance,
    projectNames,
    contracts,
    aging,
    incidents,
    pendingApprovals,
    workflowDefinitions,
  });

  if (alerts.length === 0) return null;

  const highCount = alerts.filter((a) => a.severity === "high").length;

  return (
    <Card style={{ marginBottom: 20, borderColor: highCount > 0 ? "var(--sf-brick)" : "var(--sf-amber)" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
        <h2 style={{ fontSize: 15, fontWeight: 700 }}>Alerts</h2>
        <span style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>
          {alerts.length} item{alerts.length === 1 ? "" : "s"} need attention
        </span>
      </div>
      <div>
        {alerts.map((alert) => (
          <AlertRow key={alert.id} alert={alert} />
        ))}
      </div>
    </Card>
  );
}
