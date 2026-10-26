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

**(Closed) Editing a draft in place.** `PUT /v1/workflow/definitions/<id>`
(`workflow:admin`) accepts any subset of `workflow_name`, `description`,
`steps` (steps, when sent, replace the whole chain; the trigger pair is fixed,
and sending it is a 422). It is allowed only while the definition is a true
draft: inactive, and never used by any approval instance (a used definition's
steps are referenced by its history, so editing them would rewrite it). Both
refusals are 409 with an explanation. The single-definition GET now returns
`editable`, which drives an "Edit draft" button on the detail page and the
`/workflows/:id/edit` page (the builder in edit mode, trigger locked, Save
Draft = PUT, Publish = PUT then activate). Anything not editable still goes
through "New version". Not done: the list view does not show an `editable`
flag, and there is no edit-conflict detection if two admins edit the same
draft at once (last save wins).

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

**(Closed) Valid trigger list.** `GET /v1/workflow/valid-triggers`
(`workflow:admin`) returns the module/entity pairs that really start a
workflow, from the registry in `backend/app/workflow/triggers.py`. The builder
reads it and falls back to its built-in list if the request fails. The
registry is hand-kept but guarded: `tests/test_workflow_triggers.py` scans the
module services for `get_active_workflow(...)` call sites and fails if the
registry and the code disagree, so adding an approval integration without
registering it breaks the build instead of leaving the builder stale. The
"custom" free-text option remains as an escape hatch, and a custom pair still
never fires unless code calls it.

**(Closed on the backend in migration 0052 -- see WORKFLOW_APPROVAL_GAPS.md. The builder UI does not yet expose the escalation target.) BACKEND GAP: no timeout/escalation scheduler.**
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
