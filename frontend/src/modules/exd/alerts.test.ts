import { describe, it, expect, vi, afterEach } from "vitest";
import { computeExecutiveAlerts } from "./alerts";
import type { WorkflowInstance, WorkflowDefinition } from "../workflow/types";
import type { ARAPAging } from "./hooks";

function emptyAging(): ARAPAging {
  const emptyBands = { current: [], "1_30_days": [], "31_60_days": [], "61_90_days": [], over_90_days: [] };
  return { accounts_receivable: { ...emptyBands }, accounts_payable: { ...emptyBands } };
}

describe("computeExecutiveAlerts", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns no alerts when every input is genuinely absent", () => {
    expect(computeExecutiveAlerts({})).toEqual([]);
  });

  it("flags a real project as delayed when SPI is below the real threshold", () => {
    const alerts = computeExecutiveAlerts({
      performance: [{ project_id: "p1", cpi: "1.0", spi: "0.75" }],
      projectNames: [{ id: "p1", name: "Lekki Tower" }],
    });
    expect(alerts).toHaveLength(1);
    expect(alerts[0].type).toBe("project_delayed");
    expect(alerts[0].title).toContain("Lekki Tower");
  });

  it("flags a real project as over budget when CPI is below the real threshold", () => {
    const alerts = computeExecutiveAlerts({
      performance: [{ project_id: "p1", cpi: "0.8", spi: "1.0" }],
      projectNames: [{ id: "p1", name: "Lekki Tower" }],
    });
    expect(alerts).toHaveLength(1);
    expect(alerts[0].type).toBe("project_over_budget");
  });

  it("does not flag a real project performing within the real threshold", () => {
    const alerts = computeExecutiveAlerts({ performance: [{ project_id: "p1", cpi: "1.05", spi: "0.95" }] });
    expect(alerts).toHaveLength(0);
  });

  it("uses a real, honest fallback name when no matching project is found", () => {
    const alerts = computeExecutiveAlerts({ performance: [{ project_id: "p1", cpi: "0.5", spi: "1.0" }] });
    expect(alerts[0].title).toBe("A project is over budget");
  });

  it("flags a real active contract expiring within the real window", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-24T00:00:00Z"));
    const alerts = computeExecutiveAlerts({
      contracts: [{ id: "c1", contract_number: "CTR-001", status: "active", completion_date: "2026-09-10" }],
    });
    expect(alerts).toHaveLength(1);
    expect(alerts[0].type).toBe("contract_expiring");
  });

  it("does not flag a real contract expiring outside the real window", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-24T00:00:00Z"));
    const alerts = computeExecutiveAlerts({
      contracts: [{ id: "c1", contract_number: "CTR-001", status: "active", completion_date: "2027-01-01" }],
    });
    expect(alerts).toHaveLength(0);
  });

  it("does not flag a real already-completed contract even if its completion date is near", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-24T00:00:00Z"));
    const alerts = computeExecutiveAlerts({
      contracts: [{ id: "c1", contract_number: "CTR-001", status: "completed", completion_date: "2026-09-01" }],
    });
    expect(alerts).toHaveLength(0);
  });

  it("gives a contract expiring within a week real high severity", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-24T00:00:00Z"));
    const alerts = computeExecutiveAlerts({
      contracts: [{ id: "c1", contract_number: "CTR-001", status: "active", completion_date: "2026-08-28" }],
    });
    expect(alerts[0].severity).toBe("high");
  });

  it("flags every real overdue item in the AR bands as a certificate overdue alert", () => {
    const aging = emptyAging();
    aging.accounts_receivable["1_30_days"] = [{ certificate_id: "cert1", certificate_number: "PC-001", amount: "50000", due_date: "2026-08-01" }];
    const alerts = computeExecutiveAlerts({ aging });
    expect(alerts).toHaveLength(1);
    expect(alerts[0].type).toBe("certificate_overdue");
    expect(alerts[0].title).toContain("PC-001");
  });

  it("does not flag real current (not-yet-due) AR items", () => {
    const aging = emptyAging();
    aging.accounts_receivable.current = [{ certificate_id: "cert1", certificate_number: "PC-001", amount: "50000", due_date: null }];
    const alerts = computeExecutiveAlerts({ aging });
    expect(alerts).toHaveLength(0);
  });

  it("flags every real overdue item in the AP bands as a payment issue alert, distinct from certificate overdue", () => {
    const aging = emptyAging();
    aging.accounts_payable.over_90_days = [{ invoice_id: "inv1", invoice_number: "AP-001", amount: "75000", due_date: "2026-01-01" }];
    const alerts = computeExecutiveAlerts({ aging });
    expect(alerts).toHaveLength(1);
    expect(alerts[0].type).toBe("payment_issue");
  });

  it("flags a real open safety incident", () => {
    const alerts = computeExecutiveAlerts({
      incidents: [{ id: "i1", project_id: "p1", classification: "first_aid", description: "Minor cut", status: "open", corrective_action_id: null, occurred_at: null }],
    });
    expect(alerts).toHaveLength(1);
    expect(alerts[0].type).toBe("safety_incident");
    expect(alerts[0].severity).toBe("medium");
  });

  it("does not flag a real closed safety incident", () => {
    const alerts = computeExecutiveAlerts({
      incidents: [{ id: "i1", project_id: "p1", classification: "first_aid", description: "Minor cut", status: "closed", corrective_action_id: null, occurred_at: null }],
    });
    expect(alerts).toHaveLength(0);
  });

  it("gives a real lost-time or fatality incident high severity", () => {
    const alerts = computeExecutiveAlerts({
      incidents: [{ id: "i1", project_id: "p1", classification: "lost_time", description: "Fall from height", status: "open", corrective_action_id: null, occurred_at: null }],
    });
    expect(alerts[0].severity).toBe("high");
  });

  it("flags a real overdue pending approval, using the same real SLA computation as the Approval Center", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-24T12:00:00Z"));
    const definition: WorkflowDefinition = {
      id: "wf1", module_name: "prc", entity_type: "purchase_request", workflow_name: "PR Approval",
      description: null, active: true, version: 1, created_at: "2026-01-01T00:00:00Z", created_by: null,
      updated_at: "2026-01-01T00:00:00Z", updated_by: null,
      steps: [{ id: "s1", step_number: 1, name: "Finance", approver_type: "specific_role", required_role_id: "r1", timeout_hours: 4, auto_escalate: false, allow_skip: false, parallel: false }],
    };
    const instance: WorkflowInstance = {
      id: "inst1", workflow_id: "wf1", module_name: "prc", entity_type: "purchase_request", entity_id: "e1",
      status: "pending", current_step_number: 1, amount: null, initiated_by: "u1", created_at: "2026-08-24T00:00:00Z", actions: [],
    };
    const alerts = computeExecutiveAlerts({ pendingApprovals: [instance], workflowDefinitions: [definition] });
    expect(alerts).toHaveLength(1);
    expect(alerts[0].type).toBe("approval_overdue");
  });

  it("does not flag a real pending approval still within its SLA", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-24T01:00:00Z"));
    const definition: WorkflowDefinition = {
      id: "wf1", module_name: "prc", entity_type: "purchase_request", workflow_name: "PR Approval",
      description: null, active: true, version: 1, created_at: "2026-01-01T00:00:00Z", created_by: null,
      updated_at: "2026-01-01T00:00:00Z", updated_by: null,
      steps: [{ id: "s1", step_number: 1, name: "Finance", approver_type: "specific_role", required_role_id: "r1", timeout_hours: 24, auto_escalate: false, allow_skip: false, parallel: false }],
    };
    const instance: WorkflowInstance = {
      id: "inst1", workflow_id: "wf1", module_name: "prc", entity_type: "purchase_request", entity_id: "e1",
      status: "pending", current_step_number: 1, amount: null, initiated_by: "u1", created_at: "2026-08-24T00:00:00Z", actions: [],
    };
    const alerts = computeExecutiveAlerts({ pendingApprovals: [instance], workflowDefinitions: [definition] });
    expect(alerts).toHaveLength(0);
  });

  it("does not attempt approval-overdue alerts when only one of the two required inputs is present", () => {
    const instance: WorkflowInstance = {
      id: "inst1", workflow_id: "wf1", module_name: "prc", entity_type: "purchase_request", entity_id: "e1",
      status: "pending", current_step_number: 1, amount: null, initiated_by: "u1", created_at: "2020-01-01T00:00:00Z", actions: [],
    };
    const alerts = computeExecutiveAlerts({ pendingApprovals: [instance] });
    expect(alerts).toHaveLength(0);
  });

  it("combines real alerts across every independent source at once", () => {
    const aging = emptyAging();
    aging.accounts_payable["1_30_days"] = [{ invoice_id: "inv1", invoice_number: "AP-001", amount: "1000", due_date: "2026-08-01" }];
    const alerts = computeExecutiveAlerts({
      performance: [{ project_id: "p1", cpi: "0.5", spi: "0.5" }],
      incidents: [{ id: "i1", project_id: "p1", classification: "first_aid", description: "x", status: "open", corrective_action_id: null, occurred_at: null }],
      aging,
    });
    const types = alerts.map((a) => a.type).sort();
    expect(types).toEqual(["payment_issue", "project_delayed", "project_over_budget", "safety_incident"]);
  });
});
