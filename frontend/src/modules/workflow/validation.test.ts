import { describe, it, expect } from "vitest";
import { validateWorkflowDraft, type WorkflowDraft } from "./validation";
import type { WorkflowStep } from "./types";

function realStep(overrides: Partial<WorkflowStep> = {}): WorkflowStep {
  return {
    step_number: 1,
    name: "Finance Approval",
    approver_type: "specific_role",
    required_role_id: "role-1",
    auto_escalate: false,
    allow_skip: false,
    parallel: false,
    ...overrides,
  };
}

function realDraft(overrides: Partial<WorkflowDraft> = {}): WorkflowDraft {
  return {
    workflow_name: "Purchase Request Approval",
    module_name: "prc",
    entity_type: "purchase_request",
    steps: [realStep()],
    ...overrides,
  };
}

describe("validateWorkflowDraft", () => {
  it("accepts a real, complete, valid draft with no errors", () => {
    expect(validateWorkflowDraft(realDraft())).toEqual([]);
  });

  it("requires a workflow name", () => {
    const errors = validateWorkflowDraft(realDraft({ workflow_name: "" }));
    expect(errors.some((e) => e.includes("Workflow name"))).toBe(true);
  });

  it("requires a real trigger (module and entity type)", () => {
    const errors = validateWorkflowDraft(realDraft({ module_name: "", entity_type: "" }));
    expect(errors.some((e) => e.includes("trigger"))).toBe(true);
  });

  it("requires at least one step", () => {
    const errors = validateWorkflowDraft(realDraft({ steps: [] }));
    expect(errors.some((e) => e.includes("At least one approval step"))).toBe(true);
  });

  it("rejects step numbers with a gap", () => {
    const errors = validateWorkflowDraft(
      realDraft({ steps: [realStep({ step_number: 1 }), realStep({ step_number: 3 })] })
    );
    expect(errors.some((e) => e.includes("sequential"))).toBe(true);
  });

  it("allows two steps sharing the same step_number (a real parallel group)", () => {
    const errors = validateWorkflowDraft(
      realDraft({
        steps: [
          realStep({ step_number: 1, name: "Approver A", parallel: true }),
          realStep({ step_number: 1, name: "Approver B", parallel: true }),
        ],
      })
    );
    expect(errors).toEqual([]);
  });

  it("requires a name on every step", () => {
    const errors = validateWorkflowDraft(realDraft({ steps: [realStep({ name: "" })] }));
    expect(errors.some((e) => e.includes("name is required"))).toBe(true);
  });

  it("requires a real user when approver_type is specific_user", () => {
    const errors = validateWorkflowDraft(
      realDraft({ steps: [realStep({ approver_type: "specific_user", specific_user_id: undefined, required_role_id: undefined })] })
    );
    expect(errors.some((e) => e.includes("approver user"))).toBe(true);
  });

  it("requires a real role when approver_type is specific_role", () => {
    const errors = validateWorkflowDraft(realDraft({ steps: [realStep({ required_role_id: undefined })] }));
    expect(errors.some((e) => e.includes("approver role"))).toBe(true);
  });

  it("rejects a minimum amount greater than the maximum", () => {
    const errors = validateWorkflowDraft(
      realDraft({ steps: [realStep({ minimum_amount: "5000000", maximum_amount: "1000000" })] })
    );
    expect(errors.some((e) => e.includes("minimum amount"))).toBe(true);
  });

  it("accepts a real, valid amount range", () => {
    const errors = validateWorkflowDraft(
      realDraft({ steps: [realStep({ minimum_amount: "1000000", maximum_amount: "5000000" })] })
    );
    expect(errors).toEqual([]);
  });

  it("rejects reject_to_step pointing at a step that doesn't exist", () => {
    const errors = validateWorkflowDraft(realDraft({ steps: [realStep({ step_number: 1, reject_to_step: 4 })] }));
    expect(errors.some((e) => e.includes("does not match any real step"))).toBe(true);
  });

  it("rejects reject_to_step pointing forward or at itself (a real cycle risk)", () => {
    const errors = validateWorkflowDraft(
      realDraft({
        steps: [
          realStep({ step_number: 1, reject_to_step: 1 }),
          realStep({ step_number: 2, name: "CEO Approval" }),
        ],
      })
    );
    expect(errors.some((e) => e.includes("earlier step"))).toBe(true);
  });

  it("accepts a real, valid reject_to_step pointing to a genuinely earlier step", () => {
    const errors = validateWorkflowDraft(
      realDraft({
        steps: [
          realStep({ step_number: 1, name: "Finance" }),
          realStep({ step_number: 2, name: "CEO", reject_to_step: 1 }),
        ],
      })
    );
    expect(errors).toEqual([]);
  });

  it("reports multiple real problems at once, not just the first one found", () => {
    const errors = validateWorkflowDraft(realDraft({ workflow_name: "", steps: [] }));
    expect(errors.length).toBeGreaterThanOrEqual(2);
  });
});
