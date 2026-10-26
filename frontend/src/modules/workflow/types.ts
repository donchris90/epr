/** Real types matching backend/app/workflow/schemas.py exactly --
 * checked directly against the actual Marshmallow schemas before
 * writing these, not guessed. */

export const APPROVER_TYPES = ["specific_user", "specific_role"] as const;
export type ApproverType = (typeof APPROVER_TYPES)[number];

export const INSTANCE_STATUSES = ["pending", "approved", "rejected", "cancelled"] as const;
export type InstanceStatus = (typeof INSTANCE_STATUSES)[number];

export const ACTION_TYPES = ["approve", "reject", "return", "comment", "delegate", "escalate", "cancel"] as const;
export type ActionType = (typeof ACTION_TYPES)[number];

export interface WorkflowStep {
  id?: string; // absent on a step not yet saved to the backend
  step_number: number;
  name: string;
  approver_type: ApproverType;
  specific_user_id?: string | null;
  required_role_id?: string | null;
  minimum_amount?: string | null;
  maximum_amount?: string | null;
  timeout_hours?: number | null;
  auto_escalate: boolean;
  allow_skip: boolean;
  parallel: boolean;
  reject_to_step?: number | null;
  /** Who the step escalates to (backend migration 0052). Either or
   * both may be set; an escalated step can also be actioned by them. */
  escalate_to_user_id?: string | null;
  escalate_to_role_id?: string | null;
}

export interface WorkflowDefinition {
  id: string;
  module_name: string;
  entity_type: string;
  workflow_name: string;
  description: string | null;
  active: boolean;
  version: number;
  created_at: string;
  created_by: string | null;
  updated_at: string;
  updated_by: string | null;
  steps: WorkflowStep[];
  /** Present on the single-definition GET: true for a draft that no approval has used. */
  editable?: boolean;
}

export interface WorkflowAction {
  id: string;
  step_number: number;
  action_type: ActionType;
  actor_id: string;
  old_status: string | null;
  new_status: string | null;
  comment: string | null;
  delegated_to: string | null;
  created_at: string;
}

export interface WorkflowInstance {
  id: string;
  workflow_id: string;
  module_name: string;
  entity_type: string;
  entity_id: string;
  status: InstanceStatus;
  current_step_number: number;
  amount: string | null;
  initiated_by: string;
  created_at: string;
  /** Backend-stored due date of the CURRENT step (null if the step has
   * no timeout). Optional so older payloads/fixtures without it still
   * type-check; computeSlaInfo falls back to deriving it. */
  step_due_at?: string | null;
  /** Set when the current step has been escalated; cleared when the
   * instance moves to another step. */
  escalated_at?: string | null;
  actions: WorkflowAction[];
}

/** WorkflowAction.actor_id for escalations performed by the
 * scheduler rather than a person (backend SYSTEM_ACTOR_ID). */
export const SYSTEM_ACTOR_ID = "00000000-0000-0000-0000-000000000000";

/** Real, known (module_name, entity_type) pairs -- verified directly
 * against real call sites (grep for get_active_workflow/
 * start_workflow_instance across backend/app/modules/), not guessed.
 * Confirmed real integrations only: prc/purchase_request,
 * ctm/contract_amendment, est/budget_revision, hse/permit_to_work.
 * backend/app/workflow/schemas.py itself leaves both fields as
 * free-text strings (no backend-enforced list exists), so this is a
 * frontend-only convenience for the confirmed cases, not a hard
 * constraint -- a workflow can still be defined for any other
 * module/entity pair by typing a custom value, though it would never
 * actually trigger unless some module's code calls
 * start_workflow_instance for that exact pair.
 *
 * Fallback snapshot only: the live list comes from
 * GET /v1/workflow/valid-triggers (backend app/workflow/triggers.py,
 * guarded by a test against the real call sites). */
export const KNOWN_MODULE_ENTITY_PAIRS: { module_name: string; entity_type: string; label: string }[] = [
  { module_name: "prc", entity_type: "purchase_request", label: "Procurement — Purchase Request" },
  { module_name: "ctm", entity_type: "contract_amendment", label: "Contracts — Contract Amendment" },
  { module_name: "est", entity_type: "budget_revision", label: "Estimating — Budget Revision" },
  { module_name: "hse", entity_type: "permit_to_work", label: "HSE — Permit to Work" },
];
