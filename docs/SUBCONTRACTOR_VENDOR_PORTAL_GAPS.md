# Subcontractor Portal & Vendor Portal — Backend Gaps

Written the same way `CLIENT_PORTAL_GAPS.md` and `WORKFLOW_BUILDER_GAPS.md`
were: an honest account of what this work found, built, and closed
safely, and what remains genuinely unbacked -- not a feature
announcement.

## What's real

Both portals now have complete, working authentication (login,
refresh, logout, change-password, identity-spoofing protection),
replicating the Client Portal's own already-proven pattern as closely
as possible rather than inventing a new one for each. Confirmed
genuinely missing before building: neither `SubcontractorPortalUser`
nor `VendorPortalUser` had a password of any kind, and every real
route required the internal staff `@require_permission` grant --
staff acting on a subcontractor/vendor's behalf, with no way for
either to ever obtain a session token themselves.

Real, working features on top of that: a subcontractor can view their
own agreements, submit progress against one, view real payment
certificates, and submit/track claims. A vendor can view their own
purchase orders, acknowledge one with a committed delivery date, and
submit/track invoices.

## Real, small backend additions made while building this

Two genuine gaps found and closed, not invented functionality:

- `GET /v1/scp/portal-users/<id>/agreements` and its detail
  counterpart -- the only prior agreement-listing endpoint was
  staff-only and tenant-wide with no subcontractor filter at all.
- `GET /v1/vnp/vendor-users/<id>/purchase-orders` -- the only prior
  capability was acknowledging a PO already known by id; nothing let
  a vendor discover which POs exist for them at all.

Both are safe, direct, ownership-scoped queries over columns
(`subcontractor_id`, `vendor_id`) that already existed -- not new
business logic.

## Genuine gaps -- not built, and not faked

**Self-service "forgot password" -- now built for both portals** (migration
`0053_portal_pwd_reset`). `POST /v1/scp|vnp/auth/forgot-password` always
returns the same 200 (no account enumeration, 5/hour) and emails a
single-use, 1-hour link (`/subcontractor/reset-password?token=...`,
`/vendor/reset-password?token=...`); `POST .../auth/reset-password`
(10/hour) sets the new password. Only a SHA-256 hash of the token is
stored (`portal_password_reset_tokens`, outside RLS). A reset sets
`password_changed_at`, carried in portal tokens as `pwd_ts` and checked
on refresh and every request, so all earlier sessions stop working.
Portal sessions issued before this change have no `portal_kind` claim;
they keep working until their next refresh, which re-checks them.
Remaining: the Client Portal (CLP) still has no equivalent.

**Notification bell -- now built for both portals.** Staff decisions now call
`notify()` for the affected portal users (`app/notifications/portal.py`):
claim approved/rejected/under review and payment certificate issued
(subcontractor); banking-details change approved/rejected (vendor). The
portals read them through the ordinary `/v1/notifications` routes with the
portal token, via a shared bell and a full list page. Remaining: no
notifications yet for PO issued, RFQ invitation, progress verification or
retention release; no email copy (in-app only).

**Documents pages -- now built for both portals.** Portal tokens still do not
hold `documents:write`. Instead, each portal has its own scoped routes
(`/v1/scp/portal-users/<id>/documents/...` and
`/v1/vnp/vendor-users/<id>/documents/...`: upload-request, confirm, list,
download) backed by `app/documents/portal.py`, which reuses the staff S3
flow. Documents are stamped with the owning organisation
(`documents.portal_owner_type` / `portal_owner_id`, migration 0059). A portal
user sees and downloads only their own organisation's uploaded documents
(colleagues share); anything else is a 404, and staff documents are
unreachable. Allowed types: PDF, PNG, JPEG, Word, Excel, CSV; per-portal
document-type lists; 20 MB ceiling, checked on confirm from storage's own
size and the object is deleted if over. Vendors can attach an uploaded
document to an invoice (`invoice_document_id` is now ownership-checked: it
must be one of the vendor organisation's finished uploads).

Limits:
- The browser uploads straight to the bucket, so the bucket's CORS rules
  must allow `PUT` from the frontend origins (see the Render notes in the
  README); without that, uploads fail in the browser even though the API is
  fine.
- Content type is checked from the declared type, not by sniffing file
  contents, and there is no virus scanning.
- Portal users can now delete their own organisation's uploads
  (`DELETE .../documents/<id>`, Delete with a confirm step on the Documents
  page). A document that a claim or vendor invoice points at can't be deleted
  (409), because the other side may be relying on it. There is no separate
  "replace": delete (when unattached) and upload again. Staff can still delete
  through the normal documents API.
- Staff see portal uploads in the Document Library (a Source column and a
  Source filter: staff / vendor portal / subcontractor portal), each labelled
  with the organisation's name. `GET /v1/documents` accepts `source=staff|vendor|subcontractor`
  and, with a portal source, `portal_owner_id=<vendor or subcontractor id>`.
  Before this, portal uploads appeared in that list with no indication of
  where they came from. There is no per-vendor documents tab on the vendor
  record itself yet.
- Subcontractor claims can now carry one supporting document
  (`sub_claims.supporting_document_id`, migration 0060), chosen from the
  organisation's own finished uploads and ownership-checked on submit; staff
  fetch it through the normal documents API. Subcontractors have no invoice
  object (payment certificates are issued by the contractor), so claims are
  the attachment point. Progress entries carry no attachment, and a claim
  holds a single file.

Matching this session's own established pattern for every prior
portal build: no notification bell where nothing populates one, no
Documents page where no real capability backs it, no cross-entity
dashboard summary where no real aggregation endpoint exists. Every
omission above is either left out of the UI entirely or would require
a new, clearly-specified backend capability -- never faked with mock
data or a UI control that calls nothing real.

**Finance review screen for banking changes -- upgraded.** The staff screen
(Vendor Portal admin page) existed but showed a truncated vendor id and raw
JSON. It now shows the vendor name and a field-by-field comparison of the
details on file against the proposal (changed fields marked), a two-step
approve, rejection with a required reason, visible errors, and a History tab.
Approving now stores the replaced details in
`vnp_banking_change_requests.previous_banking_details` (migration 0058), shown
in History, so a bad approval can be audited. Staff list endpoint:
`GET /v1/vnp/banking-change-requests?status=pending|approved|rejected|all`.
Limits: the previous details are only recorded for approvals made after this
deploy; there is no one-click "revert", a reviewer must have the vendor submit
a new change; the proposed account number is shown in full to
`vnp:finance_approve` holders (the vendor-facing view stays masked); and
finance is now alerted when a request arrives (see below).

Finance alert: submitting a banking change notifies every active staff user in
the tenant whose role holds `vnp:finance_approve` (or `*`), as
`fin.banking_change_submitted` (Finance category), linking to the Vendor
Portal admin page. Uses the new `notify_users_with_permission` helper in
`app/notifications/services.py`, reusable for other "tell the approvers"
cases. Notification preferences apply, so a user can mute the Finance
category. Limit: it is in-app only; no email is sent.
