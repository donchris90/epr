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
  actions: WorkflowAction[];
}

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
 * BACKEND GAP: there is no endpoint returning the real, valid set of
 * (module_name, entity_type) pairs a workflow could actually attach
 * to. This list is a frontend-maintained snapshot of what's
 * confirmed wired up today, not a live, verified-against-backend
 * source of truth -- it will silently go stale if a new module
 * integration is added without updating this list too. */
export const KNOWN_MODULE_ENTITY_PAIRS: { module_name: string; entity_type: string; label: string }[] = [
  { module_name: "prc", entity_type: "purchase_request", label: "Procurement — Purchase Request" },
  { module_name: "ctm", entity_type: "contract_amendment", label: "Contracts — Contract Amendment" },
  { module_name: "est", entity_type: "budget_revision", label: "Estimating — Budget Revision" },
  { module_name: "hse", entity_type: "permit_to_work", label: "HSE — Permit to Work" },
];
