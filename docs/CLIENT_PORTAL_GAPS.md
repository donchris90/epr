# Client Portal (Module 22 / CLP) -- Gaps & Design Decisions

This document is the honest accounting the brief asked for: "If a
backend endpoint is missing, document it clearly and implement
everything else that can be completed." It covers what was found
missing, what was built to close it, and what remains genuinely
unbacked -- so the next engineer (human or Claude) doesn't have to
rediscover any of this by reading every file.

## Starting state

Before this build, `ClientPortalAdminPage.tsx` was the *entire*
client-portal frontend -- an internal staff tool (behind the normal
`ProtectedRoute`/`AppShell`, requiring `clp:approve`) for creating
client users, assigning them to projects, and answering their
requests on their behalf. There was no client-facing application at
all, and, more fundamentally:

- **`ClientPortalUser` had no password of any kind.** No
  `password_hash` column, no login endpoint, nothing.
  `authenticate_user` (`app/auth/jwt_utils.py`) only ever queried the
  internal `users` table. A comment in `app/auth/routes.py` claimed
  external portal users "authenticate through this same endpoint
  family" -- that was aspirational, not actual; it has been corrected
  in place.
- The Vendor Portal (VNP) module has the **identical** gap, still
  open. Out of scope for this build (the brief was specifically CLP),
  but worth knowing before assuming VNP is any further along.
- The existing CLP backend only ever proxied two things for a project
  the caller already knew the ID of: schedule (`get_client_schedule_view`)
  and site media (`get_client_site_media`). There was no way for a
  client to discover *which* projects they could see, and no read
  access to documents, certificates, variation orders, or invoices at
  all -- those endpoints exist (`app/documents`, `app/modules/bil`)
  but are gated by `documents:read`/`bil:read`, ordinary internal
  staff permissions with **no client-scoping of any kind** (the list
  endpoints don't even filter by project consistently). Granting a
  client token those permissions directly would have been a real
  cross-client data leak, not a hardening step.

## What was built to close this

### 1. Real client authentication (migration `0046_clp_client_auth`)

- `clp_portal_users.password_hash` -- same Argon2id scheme as the
  internal `users` table, via the already-shared
  `hash_password`/`verify_password` helpers in `app/auth/jwt_utils.py`
  (that module's own docstring anticipated exactly this: "lets other
  real account types outside `app.models.core.User` verify a
  password").
- `clp_email_index` -- **deliberately not a copy** of
  `email_tenant_index`. That table is globally unique on email
  (one staff person, one employer). `clp_portal_users` already allows
  the same client email to exist independently across multiple
  tenants (`uq_clp_portal_users_tenant_email` is scoped to
  `tenant_id`, not global) because a real client organization can
  legitimately be a client of more than one contractor at once. Login
  resolves every matching row across tenants and tries each one's
  password in turn.
- `POST /v1/clp/auth/login|refresh|logout|me|me/password` -- a
  **wholly separate token family** from `/v1/auth/*`, with its own
  `is_client: true` JWT claim. Not an extension of the staff family:
  a client session should never be structurally interchangeable with
  a staff one. `/v1/auth/refresh` now explicitly rejects a token
  carrying `is_client`, and `/v1/clp/auth/refresh` rejects one that
  doesn't -- closing the gap where refreshing on the wrong endpoint
  would silently produce a token missing the claim the identity guard
  below depends on.
- Self-service password change exists (`POST /v1/clp/auth/me/password`,
  requires the current password). **There is no self-service "forgot
  password" / reset-by-email flow.** A client who forgets their
  password today has no recovery path except asking their contractor
  to create/reset it via the admin page. Building real reset-by-email
  would need: a token-based reset link, an email template
  (`app/notifications/email.py` already has infrastructure this could
  extend), and rate limiting beyond what exists. Not built here --
  flagging it rather than shipping a half-secure version.

### 2. Two real security fixes

- **Client identity spoofing.** Every CLP route takes
  `client_user_id` as a URL parameter. Before this build, nothing
  confirmed that value was the caller's *own* identity -- a client
  token (once one existed) could pass a different client's ID and,
  as long as `assert_client_project_access` happened to pass for
  *that* client's assignment, read or act as them.
  `_get_client_user_or_404` (`app/modules/clp/routes.py`) now rejects
  any mismatch for `is_client` tokens before anything else runs. Staff
  admin tokens (no `is_client` claim) are unaffected -- they can still
  pass any `client_user_id`, which is the entire point of the admin
  page.
- **Approval target/project mismatch.** `assert_client_project_access`
  only ever checks that the client is assigned to the *claimed*
  `project_id` -- it says nothing about which project the target
  variation order or certificate actually belongs to. A client
  assigned to two projects could decide on a record from either one
  regardless of which `project_id` they claimed, as long as they knew
  the record's ID. `approve_variation_order_as_client` and
  `approve_certificate_as_client` now resolve the record's real
  project (via `Contract.project_id` for a VO, directly for a
  certificate) and reject with 403 if it doesn't match -- **fails
  closed** when a certificate has no `project_id` set at all, since
  `project_id` is optional on the internal creation schema and an
  approval is a financial commitment, not a read.

Both are covered by `backend/tests/test_clp_client_portal.py`.

### 3. New client-scoped read endpoints (all under `/v1/clp`, all going
through `assert_client_project_access`, all following the existing
module's own pattern rather than reusing the internal
`documents:read`/`bil:read`/`projects:read` endpoints directly)

- `GET .../projects` -- every project the client is assigned to
- `GET .../projects/<id>` -- client-safe detail (name, status, dates,
  contract value/currency -- **not** budget, actual cost, or margin;
  those rollups don't exist anywhere in this codebase yet, for
  internal staff either)
- `GET .../projects/<id>/progress` -- a single overall
  percent-complete number, an unweighted average of activities that
  have one; no weighting scheme exists anywhere else in this codebase
  to borrow, so an invented one would be less honest than a plain
  average
- `GET .../projects/<id>/documents` (+ `?doc_type=`) and
  `.../documents/<id>/download`
- `GET .../projects/<id>/certificates` and `.../variation-orders`
- `GET .../projects/<id>/invoices`

## Sections where the mapping to the brief's 16 items isn't 1:1

- **Drawings (item 7) is the same `Document` data as Documents (item
  6), filtered to `doc_type='drawing'`.** There is no dedicated
  drawing-register entity anywhere in this codebase -- no sheet
  numbers, no revision clouds, no superseded-by links, no versioning.
  If your team uploads drawings under a different `doc_type` value,
  they won't appear on that tab until they're uploaded (or
  re-tagged) as `'drawing'`.
- **Invoices (item 11) and Payments (item 12) are the same data.**
  There is no separate "invoice" entity in this codebase at all. A
  submitted `ProgressCertificate` (Module 18 / BIL) *is* the invoice;
  `PaymentTracking` is its payment status. `get_client_invoices`
  flattens the two into one row per certificate.
- **Issues (item 13) and Messages (item 14, "where supported") are
  both `ClientRequest`** (CLP-07: `request_type` of `rfi` or
  `service_request`). There is no dedicated issue tracker or
  messaging thread a client can safely see anywhere else in this
  codebase -- NCR and punch-list records exist (Module 15 / QMS,
  `NCR`/`PunchListItem`) but are internal QA artifacts with zero
  client-scoping infrastructure, not curated for client visibility.
  A `ClientRequest` *is* a two-message thread (the client's
  description, and staff's eventual response) -- real, working, and
  now notifies the client on resolution (see below) -- but it is not
  a general-purpose messaging system: no attachments, no threading
  beyond one reply, no read receipts, no typing indicators. Building
  real messaging would need its own entity with a message list, not
  a request/response pair.

## What's real vs. cosmetic

- **Notifications are real, not a stub.** `/v1/notifications`
  (`app/notifications/`) already scopes purely by the token's own
  `user_id` claim with **no permission check at all** -- its own
  docstring anticipated "a portal user instead of an internal one."
  A client token is a legitimate caller of it, completely unmodified.
  `resolve_client_request` now calls `notify()` when staff answers a
  client's request, so the notification bell and page have at least
  one real, functioning event behind them.
  **Not wired:** a notification when a new certificate or variation
  order becomes available for decision, or a payment-due reminder --
  those would mean adding hooks into `app/modules/bil/services.py`'s
  own submit/create paths, which was judged out of the contained,
  reviewable scope of this build. The infrastructure (`notify()`) is
  ready for it.
- **The org name shown in the client portal sidebar is cosmetic
  only**, cached in `localStorage` at login from the email domain,
  never used for any access-control decision. The backend/RLS remains
  authoritative for everything real; nothing in the frontend is
  trusted for security.

## Things intentionally left alone

- The internal `ClientPortalAdminPage.tsx` (route `/client-portal`,
  inside `AppShell`, for staff) is unchanged except for adding the
  now-required password field when creating a client user. It remains
  the tool staff use to create/manage client accounts and answer
  their requests -- nothing about it was removed or reworked.
- Vendor Portal (VNP) was not touched. It has the same missing-login
  gap as CLP did before this build; if/when it's built out, the same
  design decisions above (separate token family, `clp_email_index`
  reasoning, identity guard, ownership verification) are directly
  reusable.
