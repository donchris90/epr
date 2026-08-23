# Workflow / Approval Management — Backend Gaps

Written the same way `CLIENT_PORTAL_GAPS.md` and `WORKFLOW_BUILDER_GAPS.md`
were: an honest account of what this batch found, built, and improved
on top of the existing workflow definition/builder work
(`WORKFLOW_BUILDER_GAPS.md` already covers the definition/builder
side's own gaps — no edit endpoint, no generic condition/action node
types, no dynamic approvers, no `reject_to_step` server-side
validation — that document is still accurate and not repeated here).
This one covers what changed in this batch: the Approval Center, SLA
display, and the list/builder's Duplicate action.

## What's real

The full approve/reject/delegate/comment/cancel instance lifecycle was
already real (built earlier, backed by `POST
/v1/workflow/instances/<id>/{approve,reject,delegate,comment,cancel}`).
This batch added real filtering (module — server-side; search, date
range, SLA state — client-side, matching exactly what `GET
/v1/workflow/instances`'s own route docstring says is and isn't
supported server-side), real confirmation dialogs for
approve/reject/delegate, and a real SLA display derived entirely from
existing data.

## Real backend confirmation before building anything

- `GET /v1/workflow/instances` only supports `module_name`,
  `entity_type`, `status` as real, server-side query params
  (confirmed directly against the route's own code and docstring). No
  date, amount, requester, or approver filtering exists server-side.
  This batch's date/search/SLA filters are honestly client-side, over
  whatever the server-side filters already narrowed to — bounded by
  the same route's real 200-row cap.
- The backend's reject schema (`WorkflowDecisionSchema`) has `comment`
  as `allow_none=True`, not `required=True` — confirmed directly
  before deciding not to add a fake, frontend-only "reason required"
  validation. The task's own brief was conditional on this ("where
  backend requires it"); since it doesn't, this batch matches that
  exactly rather than inventing a stricter rule the backend doesn't
  actually enforce.

## Genuine gaps — not built, and not faked

**No SLA/due-date field exists on `WorkflowInstance` at all.**
Confirmed directly against `backend/app/workflow/models.py` — the only
real timing data is `created_at` (via `AuditMixin`). This batch's SLA
display (`modules/workflow/sla.ts`) is a real, honest *computation*
over existing data (a step's own `timeout_hours`, combined with the
most recent real `WorkflowAction` for that step, or the instance's own
`created_at` as fallback) — not a stored or backend-computed value.
"Overdue" and "Due soon" are presentational states this batch derives
client-side; nothing on the backend tracks or enforces them.

```
BACKEND GAP:
Endpoint: none directly — would need a new column
Expected model change: WorkflowInstance.step_due_at (nullable
  datetime), set by services.py whenever current_step_number changes
  (on start, approve, reject-with-return, delegate)
Expected response: WorkflowInstanceSchema exposing step_due_at
  directly
Why frontend requires it: today the frontend has to fetch every
  matching WorkflowDefinition and cross-reference the current step's
  timeout_hours against action history on every render, which is
  real but indirect — a stored, backend-computed due date would be
  more efficient and let overdue filtering happen server-side too.
```

**No escalation endpoint, target field, or status exists at all.**
`escalate` is a real, valid value in the `ACTION_TYPES` database check
constraint (`backend/app/workflow/models.py`), but confirmed directly
against `backend/app/workflow/routes.py` that no route exists to
actually trigger one — it's a vestigial, currently-unreachable enum
value. There is also no `escalate_to_user_id`/`escalate_to_role_id`
field on `WorkflowStep` at all — only `auto_escalate` (boolean) and
`timeout_hours` (int) exist. The step editor shows "Escalate after"
(real, from `timeout_hours`) honestly, and says directly in the UI
that there's no real escalation-target field and nothing enforces
this automatically — not a fake toggle implying it works.

```
BACKEND GAP:
Endpoint: POST /v1/workflow/instances/<id>/escalate
Expected request: { comment?: string }
Expected response: the updated WorkflowInstanceSchema, with a new
  action_type="escalate" WorkflowAction recorded
Expected model change: WorkflowStep.escalate_to_user_id /
  escalate_to_role_id (nullable UUID, same real
  specific_user/specific_role pattern the approver fields already
  use)
Why frontend requires it: without a real target field, there is
  nothing correct to show for "Escalation target" in the step editor
  even if a real endpoint existed; without the endpoint, "Escalation
  status" has nothing to reflect. A scheduled job checking
  step_due_at (see the gap above) and calling this endpoint
  automatically would be the real, complete feature — not built here,
  genuinely out of scope for a contained batch.
```

**No "Archived" workflow state exists, distinct from an old inactive
version.** The backend has exactly one status axis: `active`
(boolean). "Draft" (this batch's own label for `active=false`) and
"Published" (`active=true`) map cleanly to it; "Archived" as a third,
distinct state does not exist. An old, superseded version is simply an
inactive (`active=false`) row that's no longer the newest version for
its `(module_name, entity_type)` pair — viewable via the existing,
real version history, but not distinguishable from "a draft that was
never published" at the data level.

```
BACKEND GAP:
Endpoint: none — would need a new column
Expected model change: WorkflowDefinition.archived_at (nullable
  datetime) or a real status enum replacing the plain boolean
Why frontend requires it: today "Draft" and "a real, former version
  that's simply been superseded" are visually identical (both show
  as an inactive/"Draft" badge) — a real distinction would let the
  UI show "Archived" for versions that were once live but a newer
  one has since replaced them, versus "Draft" for one that's never
  been published at all.
```

**No "project" filter on the Approval Center.** `WorkflowInstance`
references its underlying record via a loose `(module_name,
entity_type, entity_id)` triple, not a `project_id` — confirmed this
is deliberate (`WorkflowInstance`'s own docstring: "a loose reference,
not a foreign key... without every module needing a hard schema
dependency on this one"). Filtering by project would mean resolving
`entity_id` against each module's own project association, which
varies by module and isn't something this generic table can answer.
Not built; genuinely not answerable without per-module logic this
batch didn't add.

**No attachments shown on the approval detail view.** Same root cause
as the project filter — a `WorkflowInstance` doesn't know what kind of
"entity" it's attached to beyond the loose reference above, and there
is no generic "list documents for this entity" endpoint spanning every
module. Real per-module document endpoints exist elsewhere in this
codebase (e.g. `documents/` module), but wiring a specific one in here
would mean hardcoding module-specific knowledge into a page that's
deliberately generic today. Not built; a genuine architectural gap
this batch didn't try to paper over.

## What was deliberately not built as a fake feature

Rather than show a misleading "Escalation: Active" badge, a fake
"escalate now" button that calls nothing real, or an empty "Attached
files" section implying the data exists but is just empty, every one
of the gaps above is either omitted entirely from the UI or shown with
an explicit, honest note about what's real and what isn't — matching
this batch's own instruction not to invent backend functionality or
pretend automatic escalation exists.
