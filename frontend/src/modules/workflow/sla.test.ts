import { describe, it, expect, vi, afterEach } from "vitest";
import { computeSlaInfo, formatTimeRemaining } from "./sla";
import type { WorkflowDefinition, WorkflowInstance } from "./types";

function realDefinition(overrides: Partial<WorkflowDefinition> = {}): WorkflowDefinition {
  return {
    id: "wf-1",
    module_name: "prc",
    entity_type: "purchase_request",
    workflow_name: "Test Workflow",
    description: null,
    active: true,
    version: 1,
    created_at: "2026-01-01T00:00:00Z",
    created_by: null,
    updated_at: "2026-01-01T00:00:00Z",
    updated_by: null,
    steps: [
      {
        id: "step-1",
        step_number: 1,
        name: "Finance Approval",
        approver_type: "specific_role",
        required_role_id: "role-1",
        timeout_hours: 24,
        auto_escalate: true,
        allow_skip: false,
        parallel: false,
      },
    ],
    ...overrides,
  };
}

function realInstance(overrides: Partial<WorkflowInstance> = {}): WorkflowInstance {
  return {
    id: "inst-1",
    workflow_id: "wf-1",
    module_name: "prc",
    entity_type: "purchase_request",
    entity_id: "entity-1",
    status: "pending",
    current_step_number: 1,
    amount: null,
    initiated_by: "user-1",
    created_at: "2026-08-23T00:00:00Z",
    actions: [],
    ...overrides,
  };
}

describe("computeSlaInfo", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns no_sla when the workflow definition is not yet loaded", () => {
    const result = computeSlaInfo(realInstance(), null);
    expect(result.state).toBe("no_sla");
  });

  it("returns no_sla when the current step has no real timeout_hours set", () => {
    const definition = realDefinition({ steps: [{ id: "s1", step_number: 1, name: "X", approver_type: "specific_role", required_role_id: "r1", auto_escalate: false, allow_skip: false, parallel: false }] });
    const result = computeSlaInfo(realInstance(), definition);
    expect(result.state).toBe("no_sla");
  });

  it("is within_sla well before the real deadline", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-23T01:00:00Z")); // 1h after instance created, 24h timeout
    const result = computeSlaInfo(realInstance(), realDefinition());
    expect(result.state).toBe("within_sla");
  });

  it("is due_soon within the real due-soon window", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-23T21:00:00Z")); // 3h left of a 24h window
    const result = computeSlaInfo(realInstance(), realDefinition());
    expect(result.state).toBe("due_soon");
  });

  it("is overdue past the real deadline", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-24T01:00:00Z")); // 1h past a 24h deadline
    const result = computeSlaInfo(realInstance(), realDefinition());
    expect(result.state).toBe("overdue");
  });

  it("uses the most recent real action for the current step as the clock start, not the instance's own created_at", () => {
    vi.useFakeTimers();
    // Instance created long ago, but returned to step 1 for rework recently
    const instance = realInstance({
      created_at: "2026-01-01T00:00:00Z",
      actions: [{ id: "a1", step_number: 1, action_type: "return", actor_id: "u1", old_status: "pending", new_status: "pending", comment: null, delegated_to: null, created_at: "2026-08-23T00:00:00Z" }],
    });
    vi.setSystemTime(new Date("2026-08-23T01:00:00Z")); // 1h after the REAL rework action, not the original creation
    const result = computeSlaInfo(instance, realDefinition());
    expect(result.state).toBe("within_sla");
  });

  it("returns no_sla for a real, already-completed instance (not pending)", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-24T01:00:00Z")); // would be overdue if still pending
    const result = computeSlaInfo(realInstance({ status: "approved" }), realDefinition());
    expect(result.state).toBe("no_sla");
  });

  it("surfaces the real auto_escalate flag from the matching step", () => {
    const result = computeSlaInfo(realInstance(), realDefinition());
    expect(result.autoEscalate).toBe(true);
  });
});

describe("formatTimeRemaining", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("formats real remaining time in hours", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-23T00:00:00Z"));
    const dueAt = new Date("2026-08-23T05:00:00Z");
    expect(formatTimeRemaining(dueAt)).toBe("5h remaining");
  });

  it("formats a real overdue duration", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-23T05:00:00Z"));
    const dueAt = new Date("2026-08-23T00:00:00Z");
    expect(formatTimeRemaining(dueAt)).toBe("5h overdue");
  });

  it("formats real remaining time in days for long durations", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-23T00:00:00Z"));
    const dueAt = new Date("2026-08-25T00:00:00Z");
    expect(formatTimeRemaining(dueAt)).toBe("2d remaining");
  });
});
