# Notification Center — Backend Gaps

Written the same way every other `*_GAPS.md` in this repo was: an
honest account of what this batch found, built, and closed safely,
and what remains genuinely unbacked.

## What's real

A complete, working notification backend already existed
(`app/notifications/`) -- in-app notifications persisted to a real
`Notification` model, list/unread-count/mark-read/mark-all-read
endpoints, all correctly scoped to the calling user (no
`@require_permission` needed, since every query is already filtered
by `g.user_id`). A working `NotificationBell` dropdown already
existed on the frontend too. This batch didn't replace either --it
added the one real, missing capability (`mark_unread`) and built a
proper, full Notification Center page on top of the same real data.

## Real, small backend addition

`mark_unread` -- a direct mirror of the already-existing `mark_read`
(`read_at = None` instead of `datetime.now()`). This batch's own
brief explicitly asks for a "mark unread" action; the backend
genuinely didn't have it. Added the service function, the route
(`POST /v1/notifications/<id>/unread`), and 2 new tests (reversing a
real read notification; the same real cross-user 404 protection
`mark_read` already has) -- both passing alongside all 8 pre-existing
tests.

## Real, honest category derivation -- not a fixed, hand-maintained list

`Notification.type` is a real, dotted, machine-readable category
(the model's own docstring: `"workflow.approval_requested"`,
`"hse.incident_raised"`) -- confirmed directly which prefixes actually
exist in this codebase today before building anything: **only 2 real
call sites exist in the entire backend**
(`app/workflow/services.py` and `app/modules/clp/services.py`),
producing exactly 4 real `type` values: `workflow.approval_requested`,
`workflow.instance_approved`, `workflow.instance_rejected`,
`clp.request_resolved`.

The frontend derives a notification's category from its real `type`
prefix (`lib/notifications.ts:categoryFor`) rather than a fixed lookup
that would need hand-updating every time a new module starts calling
`notify()`. Today this means:

- **Approvals** has real, live data (every `workflow.*` notification).
- **Projects** has some real data (`clp.*`, since client-portal
  requests are project-scoped).
- **Finance, HSE, System** are shown honestly as real tabs (per this
  batch's own explicit brief) but will show a real, honest empty
  state until something actually creates a notification with a
  `fin.*`/`bil.*`/`hse.*` prefix -- nothing today does. `System` is
  also the real, deliberate fallback for any prefix this mapping
  doesn't recognize, rather than silently dropping it.

```
BACKEND GAP:
Endpoint: none directly -- would need real notify() calls added to
  the relevant service functions across other modules (e.g. HSE
  incident creation, a project going over budget, a budget revision
  being submitted)
Why frontend requires it: without a real notify() call somewhere in
  those modules, there is nothing genuine for the Finance/HSE tabs to
  ever show beyond an honest empty state.
```

## Genuine gap -- Notification Preferences, not built at all

Confirmed directly: `NotificationSchema` has no preference fields,
and no preferences table or model exists anywhere in
`app/notifications/`. This batch's own brief is explicit: "Do not
build settings that have no backend support." No preferences UI was
built -- not a disabled placeholder, not a form that saves nowhere.

```
BACKEND GAP:
Endpoint: e.g. GET/PUT /v1/notifications/preferences
Expected model: a new NotificationPreference table (or columns on
  the existing user profile), with real per-category and per-channel
  (email vs in-app) toggles
Why frontend requires it: there is no real state to read a
  preferences UI's initial values from, and nowhere real to persist
  a change -- building the UI without this would either fake the
  data or silently do nothing when a person changes a setting.
```

## What was deliberately not built as a fake feature

No preferences screen with nothing behind it. No hidden or omitted
Finance/HSE/System tabs pretending only Approvals and Projects exist
as concepts -- they're real, valid categories per this batch's own
brief, just honestly empty today rather than faked with placeholder
data. No invented notification types to make the other tabs look
populated.
