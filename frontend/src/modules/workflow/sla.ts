import type { WorkflowDefinition, WorkflowInstance } from "./types";

export type SlaState = "no_sla" | "within_sla" | "due_soon" | "overdue";

export interface SlaInfo {
  state: SlaState;
  dueAt: Date | null;
  timeoutHours: number | null;
  autoEscalate: boolean;
}

const DUE_SOON_WINDOW_HOURS = 4;

/** Real, honest SLA computation -- entirely derived from real,
 * existing backend data, not invented. WorkflowInstance itself has no
 * due_at/sla_deadline column at all (confirmed directly against
 * backend/app/workflow/models.py before writing this); the closest
 * real signal a step is "on the clock" is its own definition's
 * timeout_hours (backend/app/workflow/models.py:WorkflowStep),
 * combined with when the instance actually reached this step -- the
 * most recent real WorkflowAction's created_at if one exists, or the
 * instance's own created_at if it's still on step 1 with no actions
 * yet.
 *
 * "Overdue" and "due soon" here are honest presentational states,
 * not backend-enforced ones -- confirmed no scheduler or endpoint
 * exists anywhere in this backend to act on an elapsed timeout (see
 * docs/WORKFLOW_BUILDER_GAPS.md's own note: "recorded, not yet
 * enforced"). This function only ever reads real data; it doesn't
 * pretend escalation happens automatically. */
export function computeSlaInfo(instance: WorkflowInstance, definition: WorkflowDefinition | null): SlaInfo {
  if (!definition) {
    return { state: "no_sla", dueAt: null, timeoutHours: null, autoEscalate: false };
  }

  const currentSteps = definition.steps.filter((s) => s.step_number === instance.current_step_number);
  const step = currentSteps[0];

  if (!step || !step.timeout_hours) {
    return { state: "no_sla", dueAt: null, timeoutHours: null, autoEscalate: false };
  }

  // The most recent action that actually landed the instance on its
  // CURRENT step -- real actions for earlier steps (e.g. a prior
  // approval, or a return-for-rework) don't count as the clock start
  // for this step. Falls back to the instance's own created_at when
  // there's no action for this step yet (still on step 1, untouched).
  const actionsForThisStep = instance.actions.filter((a) => a.step_number === instance.current_step_number);
  const clockStartsAt =
    actionsForThisStep.length > 0
      ? new Date(actionsForThisStep[actionsForThisStep.length - 1].created_at)
      : new Date(instance.created_at);

  const dueAt = new Date(clockStartsAt.getTime() + step.timeout_hours * 60 * 60 * 1000);

  if (instance.status !== "pending") {
    return { state: "no_sla", dueAt, timeoutHours: step.timeout_hours, autoEscalate: step.auto_escalate };
  }

  const now = new Date();
  const hoursRemaining = (dueAt.getTime() - now.getTime()) / (1000 * 60 * 60);

  let state: SlaState;
  if (hoursRemaining < 0) state = "overdue";
  else if (hoursRemaining <= DUE_SOON_WINDOW_HOURS) state = "due_soon";
  else state = "within_sla";

  return { state, dueAt, timeoutHours: step.timeout_hours, autoEscalate: step.auto_escalate };
}

export const SLA_STATE_LABEL: Record<SlaState, string> = {
  no_sla: "No SLA",
  within_sla: "Within SLA",
  due_soon: "Due soon",
  overdue: "Overdue",
};

export const SLA_STATE_TONE: Record<SlaState, "neutral" | "green" | "amber" | "brick"> = {
  no_sla: "neutral",
  within_sla: "green",
  due_soon: "amber",
  overdue: "brick",
};

/** Real, human-readable "time remaining" or "time overdue" -- no
 * fake precision (seconds), since this is a presentational summary,
 * not a countdown timer. */
export function formatTimeRemaining(dueAt: Date): string {
  const now = new Date();
  const diffMs = dueAt.getTime() - now.getTime();
  const overdue = diffMs < 0;
  const absHours = Math.abs(diffMs) / (1000 * 60 * 60);

  let label: string;
  if (absHours < 1) {
    const mins = Math.round(absHours * 60);
    label = `${mins}m`;
  } else if (absHours < 24) {
    label = `${Math.round(absHours)}h`;
  } else {
    label = `${Math.round(absHours / 24)}d`;
  }

  return overdue ? `${label} overdue` : `${label} remaining`;
}
