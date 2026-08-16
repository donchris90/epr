# Workflow Engine (Module 26)

A generic, cross-module approval engine. Not tied to Procurement or
any single module -- define an approval chain once for a
`(module_name, entity_type)` pair, and any module can start, query,
and act on instances of it through the same API.

This document is honest about scope: what's real and tested below,
what's deliberately deferred, and why.

## What's real

- **Sequential approval steps** -- ordered by `step_number`.
- **Parallel approval groups** -- multiple steps sharing the same
  `step_number`; the instance only advances once every applicable
  step in that group has approved.
- **Amount-based step skipping** -- a step with `minimum_amount`
  and/or `maximum_amount` set is automatically skipped if the
  instance's `amount` falls outside that range. A step with no range
  configured always applies.
- **Two approver types**: `specific_user` (a named individual) and
  `specific_role` (anyone holding that Role in the tenant, resolved
  from the acting user's own JWT `role_id` claim).
- **Reject-to-step** -- a step can be configured so a rejection there
  sends the instance back to an earlier step for rework, instead of
  terminating it. Without `reject_to_step` set, rejection is terminal.
- **Delegation** -- an approver can delegate the current step to
  another user, who can then act on it in their place. Delegation is
  scoped to that one step's current pass, not the whole workflow.
- **Cancellation** -- the instance can be withdrawn entirely (not the
  same authorization question as "are you this step's approver" --
  route-level permissions govern who can call it).
- **A fully immutable audit trail** (`WorkflowAction`) -- old status,
  new status, actor, IP address, user agent, a comment/reason, and a
  timestamp, for every single action. No update or delete route exists
  for this table, on purpose.
- **Real cross-module integration**: PRC's Purchase Request
  submit/approve flow (`app/modules/prc/services.py`) genuinely routes
  through this engine when a tenant has configured and activated one
  for `("prc", "purchase_request")`. Submitting a PR starts a real
  instance; the pre-existing single-approver `/approve` endpoint
  defers to the engine while an instance is pending (409, with the
  correct workflow endpoint to use instead in the error detail), and
  finalizes the PR's own status once the engine reports the instance
  approved. A tenant that has never configured a workflow for this
  entity type sees identical behavior to before this integration
  existed -- purely additive, nothing forced.

## What's deliberately NOT here

Stated plainly, not silently skipped:

- **No visual drag-and-drop builder.** This is an API/data-model
  layer. A builder is a substantial, separate frontend project.
- **Real email notifications, no push.** In-app notifications and
  email (via Gmail SMTP -- see `app/notifications/email.py` and
  `app/notifications/tasks.py`) both work end-to-end and are actually
  wired into this engine's approval-requested/approved/rejected
  events. SMS and push remain unimplemented -- SMS by explicit choice
  (the user chose email over SMS as the notification channel), push
  because there's no mobile app to push to yet (Module 24 is
  server-side-sync-only). Every action is also recorded and queryable
  via the API (`GET /v1/workflow/instances/pending`, etc.) regardless
  of notification delivery.
- **No automatic timeout or escalation enforcement.** `timeout_hours`
  and `auto_escalate` are real columns on `WorkflowStep` -- they're
  recorded, but nothing currently reads them to act. Enforcing this
  needs a scheduler; `app/modules/inv/tasks.py`'s Celery task is the
  established pattern for that in this codebase, not attempted here.
- **No "Manager" / "Department" / "CEO" dynamic approver types.**
  This platform has no organizational hierarchy anywhere -- no
  department table, no manager/reports-to relationship on any model,
  including Workforce Management's own Employee model. Only
  `specific_user` and `specific_role` are implemented, because those
  are the only two approver types this schema can actually resolve
  honestly. Adding org-hierarchy-based routing means building that
  hierarchy first, elsewhere in the platform.
- **No mobile integration.** No real Flutter client exists in this
  project to integrate into -- Module 24 (Mobile Field App) is
  server-side sync scaffolding only.
- **No analytics dashboard** (average approval time, bottlenecks,
  SLA tracking). The underlying data (every action, with timestamps)
  is there to build this from later; no dashboard queries or UI exist
  yet.
- **Attachments reuse the existing Document model**
  (`app/documents/`) rather than a new WorkflowAttachment table --
  this platform already has a real, tested file-upload system. Link a
  document to a workflow instance the same way any other module would
  reference one; duplicating that system here would be exactly the
  kind of "don't reuse what exists" mistake this module exists to
  avoid making elsewhere.
- **No global search UI** across requester/approver/date/amount --
  `GET /v1/workflow/instances` filters by `module_name`, `entity_type`,
  and `status` today. Filtering by requester/approver/date/amount
  would need a real join against `WorkflowAction` and query-builder
  work; left as a stated follow-up, not faked with a partial
  implementation.

## Data model

Four tables, all tenant-scoped and RLS-protected like every other
table in this platform (`ENABLE` + `FORCE ROW LEVEL SECURITY`, per
migration `0031_workflow_engine.py`):

- **`workflow_definitions`** -- one configured chain per
  `(module_name, entity_type)`, versioned. Only one version should be
  `active` at a time (a service-layer rule, not a DB constraint --
  deliberately, so an instance already in flight under an older
  version keeps making sense after a newer one is activated).
- **`workflow_steps`** -- ordered steps belonging to a definition.
- **`workflow_instances`** -- one running (or completed) approval,
  attached to a real entity in another module via a loose reference
  (`module_name`, `entity_type`, `entity_id` -- not a foreign key, the
  same established pattern used elsewhere in this codebase, e.g. PRC's
  `cbs_line_item_id`, so no module needs a hard schema dependency on
  this one).
- **`workflow_actions`** -- the immutable audit log described above.

## API

Base path `/v1/workflow`. Two permission families:

- **`workflow:admin`** -- create/activate/deactivate definitions. A
  platform-configuration action, not something every approver should
  be able to do.
- **`workflow:approve`** -- start instances, approve/reject/delegate/
  cancel/comment on them, view pending approvals and history.

| Method & Path | Purpose |
|---|---|
| `POST /definitions` | Create a new (inactive) definition with its steps |
| `GET /definitions` | List definitions, filterable by `module_name`/`entity_type` |
| `GET /definitions/<id>` | Fetch one definition with its steps |
| `POST /definitions/<id>/activate` | Activate this version (deactivates any other active version for the same module/entity type) |
| `POST /definitions/<id>/deactivate` | Deactivate |
| `POST /instances` | Start an instance for a real entity (generic entry point; see PRC's integration for the pattern a module actually adopts this with) |
| `GET /instances/pending` | Instances the calling user can currently act on |
| `GET /instances` | Filterable list/history (`module_name`, `entity_type`, `status`) |
| `GET /instances/<id>` | Fetch one instance with its full action history |
| `POST /instances/<id>/approve` | Approve the current step |
| `POST /instances/<id>/reject` | Reject the current step |
| `POST /instances/<id>/delegate` | Delegate the current step to another user |
| `POST /instances/<id>/cancel` | Withdraw the instance entirely |
| `POST /instances/<id>/comment` | Add a comment without taking a decision |

## Adopting this in another module

The pattern PRC uses, generalized -- and now proven three more times
by CTM, HSE, and EST, all following the "adding a pending state and a
`finalize` step" shape rather than PRC's pre-existing submit/approve
flow, which is the more common real-world case a new module actually
faces.

**Check for a genuine fit before integrating -- don't force it.**
Billing was checked as a candidate and rejected, correctly: its
`ProgressCertificate`/`VariationOrder`/`Claim` approvals are all
explicitly, consistently modeled as *external* client/consultant
sign-off (`approved_by` is a free-text string, not a user reference)
-- this engine's approver types only resolve internal users in the
tenant, so there's no faithful way to represent "the external client
approves" through it. The signal to check for: is `approved_by`
typed as a UUID (an internal user reference -- a real candidate) or a
free-text string (an external party -- not a fit, however tempting
the "add an approval gate" pattern looks on the surface)?

1. Add `from app.workflow import services as workflow_services` to
   the module's `services.py`.
2. At the point where an entity is submitted for approval, check
   `workflow_services.get_active_workflow(tenant_id, module_name=..., entity_type=...)`.
   If one exists, call `start_workflow_instance(...)` with the
   entity's real `id` and (if relevant) an `amount` for threshold
   routing. If the entity's real effect (a contract value change, a
   budget commitment, whatever the entity actually *does*) was
   previously applied immediately, defer that effect until approval --
   see CTM's `_apply_amendment_effects` being factored out into its
   own function specifically so it could run at two different points
   (immediately, or deferred) rather than being inlined once.
3. At the point where the module's own "approve" (or, for CTM, a new
   "finalize") logic would run, check whether a `WorkflowInstance`
   exists for this entity. If its status is `pending`, defer (return
   an error pointing at the real workflow endpoint, as PRC and CTM
   both do). If `approved`, proceed with the entity's own
   finalization -- applying whatever effect was deferred in step 2.
   If `rejected`/`cancelled`, reflect that.
4. A tenant that never configures a workflow for that
   `(module_name, entity_type)` sees no behavior change at all --
   `get_active_workflow` simply returns `None`.
5. If the entity had no status/pending concept at all before (true for
   CTM's amendments -- they were always instantaneous), a real schema
   migration adding one is likely needed, defaulting existing rows to
   whatever the pre-existing instantaneous behavior implied (CTM
   defaulted every existing amendment to `'approved'`, since that's
   what they always effectively were).

## Testing

`backend/tests/test_workflow.py` -- 12 tests covering definition
creation/activation/versioning, permission enforcement, amount-based
step skipping in both directions, sequential advancement,
reject-to-step, delegation, the pending-approvals query, the audit
trail's IP/user-agent/comment capture, and cross-tenant isolation.
Full end-to-end PRC integration (submit → blocked direct-approve →
engine approval → finalized PR) was verified manually against real
Postgres before this document was written, in addition to the
automated suite.

`backend/tests/test_ctm_amendment_workflow.py` -- 6 tests covering the
CTM integration specifically: backward compatibility with no workflow
configured, and the full pending → blocked-finalize → approved →
finalize-applies-the-mutation path for both amendment types that have
a real contract-field effect (price and time/EOT).
