import { computeSlaInfo } from "../workflow/sla";
import type { WorkflowInstance, WorkflowDefinition } from "../workflow/types";
import type { ProjectPerformance, ContractForAlerts, ARAPAging, Incident, ProjectNameLookup } from "./hooks";
import { overdueAgingItems } from "./hooks";

export type AlertType =
  | "project_delayed"
  | "project_over_budget"
  | "certificate_overdue"
  | "contract_expiring"
  | "safety_incident"
  | "approval_overdue"
  | "payment_issue";

export interface ExecutiveAlert {
  id: string;
  type: AlertType;
  severity: "high" | "medium";
  title: string;
  detail: string;
}

const CONTRACT_EXPIRING_WINDOW_DAYS = 30;
// Same real threshold already used elsewhere on this dashboard to
// flag a CPI/SPI cell red (DashboardPage.tsx's own performance
// table) -- kept consistent rather than picking a second, different
// number for the same real underlying signal.
const EVM_AT_RISK_THRESHOLD = 0.9;

/** Real executive alerts, computed entirely from data this dashboard
 * already fetches (or fetches specifically for this purpose) -- no
 * invented thresholds beyond the one already visualized elsewhere on
 * this same page, no fabricated alert types beyond what the real
 * data can actually support. Each input is independently optional
 * (undefined while loading, or if that data source's own fetch
 * failed/was denied by permissions) so one missing source doesn't
 * blank out every other alert type. See
 * docs/EXECUTIVE_DASHBOARD_GAPS.md for what's NOT alerted on and why
 * (e.g. no TRIR/LTIFR-based safety alert, since that rate has no
 * honest data source at all). */
export function computeExecutiveAlerts({
  performance,
  projectNames,
  contracts,
  aging,
  incidents,
  pendingApprovals,
  workflowDefinitions,
}: {
  performance?: ProjectPerformance[];
  projectNames?: ProjectNameLookup[];
  contracts?: ContractForAlerts[];
  aging?: ARAPAging;
  incidents?: Incident[];
  pendingApprovals?: WorkflowInstance[];
  workflowDefinitions?: WorkflowDefinition[];
}): ExecutiveAlert[] {
  const alerts: ExecutiveAlert[] = [];
  const projectNameById = new Map((projectNames ?? []).map((p) => [p.id, p.name]));

  for (const p of performance ?? []) {
    const name = projectNameById.get(p.project_id) ?? "A project";
    if (p.spi != null && Number(p.spi) < EVM_AT_RISK_THRESHOLD) {
      alerts.push({
        id: `delayed-${p.project_id}`,
        type: "project_delayed",
        severity: "high",
        title: `${name} is behind schedule`,
        detail: `SPI ${p.spi} — below the ${EVM_AT_RISK_THRESHOLD} threshold.`,
      });
    }
    if (p.cpi != null && Number(p.cpi) < EVM_AT_RISK_THRESHOLD) {
      alerts.push({
        id: `over-budget-${p.project_id}`,
        type: "project_over_budget",
        severity: "high",
        title: `${name} is over budget`,
        detail: `CPI ${p.cpi} — below the ${EVM_AT_RISK_THRESHOLD} threshold.`,
      });
    }
  }

  const now = new Date();
  for (const c of contracts ?? []) {
    if (c.status !== "active" || !c.completion_date) continue;
    const daysLeft = Math.ceil((new Date(c.completion_date).getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
    if (daysLeft >= 0 && daysLeft <= CONTRACT_EXPIRING_WINDOW_DAYS) {
      alerts.push({
        id: `contract-expiring-${c.id}`,
        type: "contract_expiring",
        severity: daysLeft <= 7 ? "high" : "medium",
        title: `Contract ${c.contract_number} expires soon`,
        detail: `Completion date in ${daysLeft} day${daysLeft === 1 ? "" : "s"} (${c.completion_date}).`,
      });
    }
  }

  if (aging) {
    for (const item of overdueAgingItems(aging.accounts_receivable)) {
      alerts.push({
        id: `certificate-overdue-${item.certificate_id}`,
        type: "certificate_overdue",
        severity: "medium",
        title: `Certificate ${item.certificate_number} is overdue`,
        detail: `${item.amount} outstanding${item.due_date ? `, due ${item.due_date}` : ""}.`,
      });
    }
    for (const item of overdueAgingItems(aging.accounts_payable)) {
      alerts.push({
        id: `payment-issue-${item.invoice_id}`,
        type: "payment_issue",
        severity: "medium",
        title: `Payable ${item.invoice_number} is overdue`,
        detail: `${item.amount} outstanding${item.due_date ? `, due ${item.due_date}` : ""}.`,
      });
    }
  }

  for (const incident of incidents ?? []) {
    if (incident.status === "open") {
      alerts.push({
        id: `safety-incident-${incident.id}`,
        type: "safety_incident",
        severity: incident.classification === "fatality" || incident.classification === "lost_time" ? "high" : "medium",
        title: "Open safety incident",
        detail: incident.description,
      });
    }
  }

  if (pendingApprovals && workflowDefinitions) {
    const definitionsById = new Map(workflowDefinitions.map((d) => [d.id, d]));
    for (const instance of pendingApprovals) {
      const definition = definitionsById.get(instance.workflow_id) ?? null;
      const sla = computeSlaInfo(instance, definition);
      if (sla.state === "overdue") {
        alerts.push({
          id: `approval-overdue-${instance.id}`,
          type: "approval_overdue",
          severity: "high",
          title: `${instance.module_name.toUpperCase()} approval is overdue`,
          detail: sla.dueAt ? `Was due ${sla.dueAt.toLocaleDateString()}.` : "Past its SLA.",
        });
      }
    }
  }

  return alerts;
}

export const ALERT_TYPE_LABEL: Record<AlertType, string> = {
  project_delayed: "Project delayed",
  project_over_budget: "Project over budget",
  certificate_overdue: "Certificate overdue",
  contract_expiring: "Contract expiring",
  safety_incident: "Safety incident",
  approval_overdue: "Approval overdue",
  payment_issue: "Payment issue",
};
