# Workflow Frontend — Real Gaps and Design Decisions

Honest accounting of what was built, what's real vs. approximated, and
what genuinely doesn't exist on the backend yet. Written the same way
`docs/CLIENT_PORTAL_GAPS.md` was — as a real engineering reference for
whoever picks this up next, not a feature announcement.

## What's real and fully backed

- List, detail, and create (draft or publish) for workflow definitions
- A real, honest node-based builder (`@xyflow/react`) representing
  exactly what the backend can execute: a linear sequence of approval
  steps, with same-step-number groups as real parallel approval, and
  `reject_to_step` as a real backward rework link
- Real validation before publish: name required, a real trigger
  (module + entity type), at least one step, every step named, every
  step has a real, resolvable approver, valid amount ranges,
  `reject_to_step` pointing only to a genuinely earlier step
- Real audit trail: `created_by`, `created_at`, `updated_at`,
  `updated_by` — the last two now genuinely populated on
  activate/deactivate (previously only existed as unused columns)
- Real version history, built entirely from the existing
  `GET /v1/workflow/definitions?module_name=&entity_type=` filter —
  old versions are never deleted, so this is genuinely real data
- Real permission gating: `workflow:admin` checked both client-side
  (hides the builder, shows a clear message) and server-side
  (`@require_permission`, unconditionally authoritative)

## Backend gaps — genuinely missing, not silently worked around

**BACKEND GAP: no update/edit endpoint for a workflow definition.**
Endpoint: `PUT /v1/workflow/definitions/<id>`
Expected request: any subset of `{workflow_name, description, steps}`
Expected response: the updated `WorkflowDefinitionSchema`
Why the frontend requires it: the brief asks for "edit draft" as a
distinct operation from "publish." Today, every "edit" is actually a
brand-new version (`POST /v1/workflow/definitions` auto-increments
`version` for the same module/entity pair) — a real, working
mechanism, but semantically different: there's no way to make a small
correction to an unpublished draft without it becoming "version 2"
even though version 1 was never live. The builder's "New version"
action on `WorkflowDetailPage` is this workaround, clearly labeled as
such, not hidden.

**BACKEND GAP: no generic condition or action node types.**
The brief asks for condition/action nodes representing arbitrary logic
(e.g. "project-based conditions", a generic "action" step). The real
backend only supports one condition shape — a step's own
`minimum_amount`/`maximum_amount` range — and has no action-node
concept at all (the workflow engine only ever produces
approve/reject/comment/delegate/escalate/cancel actions from a human
approver, never an automated downstream effect). This builder
represents amount-range as part of a step's own configuration, exactly
matching the real data model, rather than fabricating a condition/
action node with nothing real behind it.

**BACKEND GAP: no endpoint listing valid (module_name, entity_type)
pairs a workflow could actually attach to.**
Endpoint: `GET /v1/workflow/valid-triggers`
Expected response: `{data: [{module_name, entity_type, label}]}`
Why the frontend requires it: `frontend/src/modules/workflow/types.ts`
hardcodes `KNOWN_MODULE_ENTITY_PAIRS`, verified by grepping real
`get_active_workflow`/`start_workflow_instance` call sites in
`backend/app/modules/*/services.py` at the time this was written
(`prc/purchase_request`, `ctm/contract_amendment`,
`est/budget_revision`, `hse/permit_to_work`). This list will silently
go stale the next time a module integration is added without also
updating it. A "custom" free-text option exists as an escape hatch,
but a workflow built against a pair nothing actually calls will simply
never trigger, with no warning.

**BACKEND GAP: no timeout/escalation scheduler.**
`timeout_hours`/`auto_escalate` are real, storable fields — the
builder lets you set them — but nothing on the backend currently reads
them to actually escalate a stalled approval. The detail and builder
pages both say this explicitly ("recorded, not yet enforced by a
scheduler") rather than implying it works.

## Frontend-only, by design

- Search, status (active/inactive) filtering, and pagination on the
  workflow list are all client-side. `GET /v1/workflow/definitions`
  only supports `module_name`/`entity_type` filters, no text search or
  limit/offset. Reasonable for the realistic number of workflow
  definitions a tenant would configure (a handful per module), but a
  real limitation if that assumption stops holding.
- All the validation in `modules/workflow/validation.ts` beyond the
  two rules now enforced server-side (steps non-empty, every step has
  a real approver) is frontend-only. The brief itself frames
  "prevent publishing invalid workflows" as a frontend responsibility
  layered on top of what the backend checks, not a backend gap.

## A real bug found and fixed while building this, unrelated to workflow itself

`ProjectSelect`, and the two new pickers built alongside it
(`UserSelect`, `RoleSelect`), didn't accept or forward an `id` prop.
The shared `Field` component (`components/ui.tsx`) clones its child
with an injected `id` for real `<label for>` association — silently
dropped for all three, breaking both `getByLabelText` in tests and
real screen-reader label association. Fixed in all three, not just
the two new ones, since it's the same root cause.
