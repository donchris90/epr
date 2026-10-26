import type { WorkflowDefinition, WorkflowInstance } from "./types";

export type SlaState = "no_sla" | "within_sla" | "due_soon" | "overdue";

export interface SlaInfo {
  state: SlaState;
  dueAt: Date | null;
  timeoutHours: number | null;
  autoEscalate: boolean;
}

const DUE_SOON_WINDOW_HOURS = 4;

/** Real, honest SLA computation.
 *
 * Preferred source: the backend's stored `step_due_at` (migration
 * 0052), set from the step's timeout_hours whenever the instance
 * enters a step. When an instance doesn't carry it (older payloads),
 * this falls back to deriving the due date from the step's
 * timeout_hours plus when the instance reached the step -- the most
 * recent action for this step, or the instance's created_at.
 *
 * "Overdue" and "due soon" are display states computed from the
 * current time. Whether an overdue step is then auto-escalated is the
 * backend's job (hourly task, only for steps with auto_escalate on and
 * an escalation target); `autoEscalate` here just reports the flag. */
export function computeSlaInfo(instance: WorkflowInstance, definition: WorkflowDefinition | null): SlaInfo {
  if (!definition) {
    return { state: "no_sla", dueAt: null, timeoutHours: null, autoEscalate: false };
  }

  const currentSteps = definition.steps.filter((s) => s.step_number === instance.current_step_number);
  const step = currentSteps[0];

  if (!step || !step.timeout_hours) {
    return { state: "no_sla", dueAt: null, timeoutHours: null, autoEscalate: false };
  }

  const autoEscalate = currentSteps.some((s) => s.auto_escalate);

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

  const storedDue = instance.step_due_at ? new Date(instance.step_due_at) : null;
  const dueAt =
    storedDue && !Number.isNaN(storedDue.getTime())
      ? storedDue
      : new Date(clockStartsAt.getTime() + step.timeout_hours * 60 * 60 * 1000);

  if (instance.status !== "pending") {
    return { state: "no_sla", dueAt, timeoutHours: step.timeout_hours, autoEscalate };
  }

  const now = new Date();
  const hoursRemaining = (dueAt.getTime() - now.getTime()) / (1000 * 60 * 60);

  let state: SlaState;
  if (hoursRemaining < 0) state = "overdue";
  else if (hoursRemaining <= DUE_SOON_WINDOW_HOURS) state = "due_soon";
  else state = "within_sla";

  return { state, dueAt, timeoutHours: step.timeout_hours, autoEscalate };
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
