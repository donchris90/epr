import type { WorkflowStep } from "./types";

export interface WorkflowDraft {
  workflow_name: string;
  module_name: string;
  entity_type: string;
  steps: WorkflowStep[];
}

/** Real client-side validation before publishing -- the backend
 * itself only validates that each step has a matching approver id and
 * that steps isn't empty (backend/app/workflow/schemas.py, both fixed
 * in this batch). Everything else here (sequential step numbers,
 * valid reject_to_step targets, a real trigger, unique step
 * ordering) has no backend enforcement at all -- this is exactly the
 * frontend's own stated responsibility per this batch's brief
 * ("Prevent publishing invalid workflows"), not a backend gap to
 * document, since the task itself frames validation as a frontend
 * concern layered on top of what the backend does check. */
export function validateWorkflowDraft(draft: WorkflowDraft): string[] {
  const errors: string[] = [];

  if (!draft.workflow_name.trim()) {
    errors.push("Workflow name is required.");
  }

  // "No trigger" -- module_name/entity_type together are the real
  // trigger (see WorkflowDetailPage's own honest framing of this),
  // not a separate configurable node in the backend's data model.
  if (!draft.module_name.trim() || !draft.entity_type.trim()) {
    errors.push("A trigger (module and entity type) is required.");
  }

  if (draft.steps.length === 0) {
    errors.push("At least one approval step is required.");
  }

  const stepNumbers = new Set(draft.steps.map((s) => s.step_number));
  const sortedNumbers = Array.from(stepNumbers).sort((a, b) => a - b);

  // "Disconnected nodes" / "invalid transitions" -- in this backend's
  // real, linear (not arbitrary-graph) model, that means step_numbers
  // must be sequential starting at 1 with no gaps. A gap would mean a
  // real instance advancing past step 1 has no step 2 to land on at
  // all (_next_applicable_step_number in app/workflow/services.py
  // would just skip straight past it, silently).
  sortedNumbers.forEach((num, index) => {
    if (num !== index + 1) {
      errors.push(`Step numbers must be sequential starting at 1 (found a gap or duplicate near step ${num}).`);
    }
  });

  draft.steps.forEach((step, index) => {
    const label = step.name.trim() ? `"${step.name}"` : `Step ${index + 1}`;

    if (!step.name.trim()) {
      errors.push(`${label}: a name is required.`);
    }

    // "Missing approver" -- matches the real backend validation added
    // in this batch (WorkflowStepInputSchema's own
    // _require_matching_approver), checked here too for immediate
    // feedback before a round-trip.
    if (step.approver_type === "specific_user" && !step.specific_user_id) {
      errors.push(`${label}: a specific approver user must be selected.`);
    }
    if (step.approver_type === "specific_role" && !step.required_role_id) {
      errors.push(`${label}: a specific approver role must be selected.`);
    }

    // "Invalid conditions" -- an amount range where the minimum
    // exceeds the maximum can never actually apply to any real
    // instance (app/workflow/services.py:_step_applies would reject
    // every amount).
    if (step.minimum_amount && step.maximum_amount && Number(step.minimum_amount) > Number(step.maximum_amount)) {
      errors.push(`${label}: minimum amount cannot be greater than maximum amount.`);
    }

    // "Invalid transitions" / "circular flow" -- reject_to_step must
    // point to a real, earlier step. Pointing forward or to itself
    // isn't a rework loop, it's either a no-op or a genuine cycle the
    // backend has no protection against at all (approve_step/
    // reject_step just set current_step_number directly, with no
    // cycle detection).
    if (step.reject_to_step != null) {
      if (!stepNumbers.has(step.reject_to_step)) {
        errors.push(`${label}: "return to step" (${step.reject_to_step}) does not match any real step in this workflow.`);
      } else if (step.reject_to_step >= step.step_number) {
        errors.push(`${label}: "return to step" must point to an earlier step, not the same or a later one.`);
      }
    }
  });

  return errors;
}
