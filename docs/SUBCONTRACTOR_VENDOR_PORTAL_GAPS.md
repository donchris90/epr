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

**No self-service "forgot password" flow for either portal.** Same
gap already documented for the Client Portal (`CLIENT_PORTAL_GAPS.md`)
-- only staff-initiated password creation exists (via
`POST /v1/scp/portal-users` / `POST /v1/vnp/vendor-users`). Building a
real one needs a token-based reset link, an email template, and rate
limiting beyond what exists today for either portal; flagged rather
than shipped half-secure.

**No notification bell in either portal.** Confirmed directly against
`backend/app/modules/scp/services.py` and
`backend/app/modules/vnp/services.py` that neither module calls
`notify()` anywhere at all -- unlike the workflow engine, which does
(see `docs/WORKFLOW_APPROVAL_GAPS.md`). A bell would always show zero
and imply a feature that doesn't exist; omitted rather than faked.

```
BACKEND GAP:
Endpoint: none -- would need real notify() calls added to the
  relevant service functions (submit_progress_as_subcontractor,
  acknowledge_order, upload_vendor_invoice, etc.)
Why frontend requires it: without a real trigger somewhere in the
  backend, there is nothing genuine for a bell to ever display.
```

**No Documents page in either portal.** For SCP: confirmed zero
document capability exists anywhere in the module -- no
document-upload, document-list, or document-attachment field on any
SCP schema at all. For VNP: `UploadInvoiceSchema` does accept an
`invoice_document_id`, suggesting the intent was for an invoice to
carry a real attached file -- but confirmed directly that
`POST /v1/documents/upload-request` requires the `documents:write`
permission, which a vendor-portal token does not and should not have
(that permission is tenant-wide, far broader than "attach this one
invoice's own file"). Invoice submission in this build collects
number/amount/PO reference only; the document-attachment field is
real on the schema but genuinely unreachable safely today.

```
BACKEND GAP (SCP):
Endpoint: none exists for subcontractor-facing documents at all
Expected model change: a real document-category concept scoped to
  SCP, or a genuinely safe way to reuse the existing documents
  module without granting a portal token tenant-wide document access
Why frontend requires it: the task's own brief asks for a documents
  section; there is nothing real to build it against today.

BACKEND GAP (VNP):
Endpoint: a narrower permission than documents:write -- e.g.
  documents:write:own-uploads, or a dedicated
  POST /v1/vnp/vendor-users/<id>/invoices/<id>/attach-document route
  that internally uses staff-level document creation but is scoped
  to only the calling vendor's own invoice
Why frontend requires it: invoice_document_id already exists on the
  real schema, so the backend's own intent is clear -- what's
  missing is a safe way for a vendor-portal token to actually
  populate it without a much broader permission grant than the task
  it's meant to support.
```

**No "outstanding submissions" or cross-agreement/cross-order
aggregation on either dashboard.** Neither portal has a real backend
endpoint that computes "3 progress entries awaiting review" or
similar summaries -- each dashboard shows the real, per-agreement or
per-order data the backend actually returns, not a synthesized
rollup.

**No payment-status information on the vendor side beyond an
invoice's own internal review status.** `InvoiceUpload.status`
reflects the portal's own review workflow (pending/approved/rejected/
paid, per the real `status` field), not integration with an actual
payment/banking rail -- there is no real "payment processed on
[date]" data anywhere in this backend to show honestly.

**RFQ/quote submission (VNP-02) has no dedicated frontend page.** The
real backend endpoint (`POST /vendor-users/<id>/quotes`) exists and
was inspected, but building a genuine RFQ-invitation-aware UI (a
vendor should only ever see RFQs they were actually invited to, per
`assert_vendor_invited_to_rfq`) needs a real "list my RFQ invitations"
endpoint, which does not exist -- the same class of gap as the
purchase-order listing gap this batch already closed, but not
addressed here to keep this batch's scope contained.

```
BACKEND GAP:
Endpoint: GET /v1/vnp/vendor-users/<id>/rfq-invitations
Expected response: the real RFQInvitation rows for this vendor,
  matching the same real ownership-scoping pattern already
  established for purchase-orders in this batch
Why frontend requires it: without it, there is no honest way to show
  a vendor "here are the RFQs you can quote on" -- only a form that
  requires already knowing a real rfq_id, which isn't a genuine
  self-service flow.
```

**Banking change requests have no vendor-facing UI in this build.**
The real submission endpoint exists
(`POST /vendor-users/<id>/banking-change-requests`) and was
inspected, but approval/rejection is explicitly staff-only
(`vnp:finance_approve`, a real, deliberate business rule per that
route's own docstring) -- a vendor-facing submission form was judged
out of this batch's contained scope, not because of a missing
capability.

## What was deliberately not built as a fake feature

Matching this session's own established pattern for every prior
portal build: no notification bell where nothing populates one, no
Documents page where no real capability backs it, no cross-entity
dashboard summary where no real aggregation endpoint exists. Every
omission above is either left out of the UI entirely or would require
a new, clearly-specified backend capability -- never faked with mock
data or a UI control that calls nothing real.
