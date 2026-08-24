# Batch 4 (WFM + SUB) — Backend & Frontend Gaps

Written the same way every other `*_GAPS.md` in this repo was: an
honest account of what this batch built and verified, and what
remains genuinely unbacked or unbuilt — not a feature list.

## Real bugs found and fixed along the way

These were found by inspection and empirical testing, not assumed —
each is a concrete, previously-broken piece of real functionality:

- **`generate_payroll_run` never filtered by timesheet status at
  all.** A `pending_approval` or even `rejected` timesheet could have
  been silently pulled into a real payroll run — a direct violation
  of this batch's own explicit requirement. Fixed with a real
  `status IN ("approved", "locked")` filter.
- **`WORKER_STATUSES` has no "terminated" value.** My first draft of
  `terminate_employee` referenced a status that would have failed
  every real call with a constraint violation. Fixed to reuse the
  real, existing `"inactive"` status.
- **`useReleaseRetention` never sent the required `stage` field.**
  Every real call would have failed with a 422.
- **`TimesheetSchema` and `LeaveRequestSchema` silently dropped real,
  important fields** (hours, rate, approval metadata, reason) no
  frontend could have ever displayed.
- **`PayrollLineSchema` never dumped the real, already-existing
  `bank_account_ref` field**, blocking any real bank export.
- **An early draft of the "post payroll to finance" hook posted an
  unbalanced double-entry** (debit gross, credit net — these differ
  by the deduction amount). Caught before it shipped and fixed to a
  real, balanced standard payroll accounting entry.
- **The pre-existing Payroll page showed a raw, truncated employee
  UUID** instead of a name — the same class of issue Batch 1
  targeted specifically. Fixed by resolving real employee names.

## What's real and complete

Every screen this batch's brief explicitly lists now exists and is
backed by a real endpoint: Workforce Dashboard, Employees (+ 9-tab
detail: Overview, Employment, Project Assignments, Attendance,
Timesheets, Leave, Training, Certifications, Competencies), Timesheets
& Leave, Payroll (+ Payroll Run detail with Payslips, Bank export,
Finance posting, Finalize), Subcontractor Dashboard, Subcontractors,
Agreement Detail (10 tabs: Overview, Scope, Progress, Measurements,
Certificates, Retention, Back Charges, Claims, Compliance,
Performance). Every employee action this batch lists is real: Create,
Edit, Assign Project, Transfer Project, Add Training/Certification/
Competency, Request/Approve/Cancel Leave, View Attendance, Terminate,
Reactivate. Every agreement action is real: Add Scope, Record
Progress, Create Measurement, Verify, Create Certificate, Add/Release
Retention, Add Back Charge, Submit/Review Claim, Upload Compliance,
Rate Contractor.

Payroll correctly enforces its one hard requirement: **only approved
or locked timesheets are ever consumed** (tested directly, not just
implied).

## Real, honest gaps — not built, and not faked

**Correct Attendance's backend endpoint and hook existed but had no
frontend UI wired to it when this document was first drafted** — found
while writing it, and closed in the same pass: `EmployeeDetailPage`'s
Attendance tab now has a real inline "Correct" action per row, using
the already-existing, already-tested `useCorrectAttendance` hook.**Bulk attendance was never built at all** — no backend endpoint, no
service function. `record_attendance` and `mark_absent` both operate
on one person at a time. A real bulk-entry screen (e.g., a whole
project's crew for one day, in one table) needs a new, real backend
endpoint that accepts a list and validates each row the same way the
single-record path does.

```
BACKEND GAP:
Endpoint: POST /v1/wfm/attendance/bulk
Expected behavior: accept a list of {employee_id or
  casual_worker_id, attendance_date, check_in_at?, check_out_at?}
  for one real project, applying the same real validation
  (record_attendance's own exactly-one-worker constraint) per row
Why frontend requires it: without it, a real bulk-entry UI would
  either fire N individual requests (a real, if inefficient, option
  not yet built) or fabricate a bulk capability the backend doesn't
  have
```

**Approve Attendance has no real state to represent it.**
`AttendanceRecord` has no `status` column at all (confirmed directly
against the model) — only `check_in_at`/`check_out_at`/
`capture_method`. There is nothing to "approve" in the real data
today; Correct Attendance (gated behind the same real `wfm:approve`
permission) is the closest real analog this backend supports.

```
BACKEND GAP:
Endpoint: none -- would need a real status column added to
  AttendanceRecord (e.g. "unverified"/"approved"), a migration, and
  a real approve action
Why frontend requires it: without a real status, there is no honest
  "pending approval" list to build a real Approve Attendance screen
  around
```

**Attendance Report is the real, filterable list
(`GET /wfm/attendance`), not a separate, aggregated report view.** It
answers "attendance for this project/employee/date," which is what
the real data supports; it does not compute rollups (e.g., attendance
rate by project over a period) — no such aggregation exists on the
backend today.

**Casual Workers is combined with Employees on one screen**
(`EmployeesPage.tsx`), not built as its own fully separate screen.
This is a real, deliberate UX choice already in place before this
batch (not left over from time pressure) — both real lists are shown
side by side rather than requiring a second page navigation for a
closely related concept. Revisiting this into two separate screens
would be straightforward if a different UX is preferred.

**Employee Detail has no Payroll, Documents, or History tab**, each
for a real, specific reason: Payroll is period-scoped, not
per-employee (a payroll run's own real detail page — built this batch
— is the right home for that data); Documents has no real
WFM-specific document link anywhere in this backend; History has no
real audit-log endpoint to read from (WFM's own `AuditMixin` records
`created_by`/`updated_by`/timestamps on each row, but there is no
endpoint that assembles a real, ordered history feed from them).

**Leave Balance shows real days taken this year by type, not a "days
remaining" figure.** No annual leave entitlement field exists
anywhere in this codebase (`Employee` has no entitlement column of
any kind) — inventing a number (e.g., a hardcoded "21 days/year")
would be fabricated data, not a real balance.

**Payroll's "Approval" step is honestly mapped onto the real
`PAYROLL_STATUSES` state machine, which only has `("draft",
"finalized")`** — no separate "approved" status exists. Rather than
inventing a third status to match this batch's own workflow diagram
literally, the real `draft` state is treated as the review/approval
stage (every section of Payroll Run Detail is available while draft),
with Finalize as the one real transition. Documented directly in the
page's own docstring.

**Payroll's "Post to Finance" posts a real, balanced, but simplified
entry** — the full gross liability only (debit expense, credit wages
payable for `total_gross`), using the real, existing generic manual
journal entry endpoint (`POST /fin/journal-entries/manual-exception`,
since no dedicated WFM→FIN payroll-posting endpoint exists). It does
not post the later, real net-cash-payment or deductions-remittance
entries: this batch has no real mapping from `StatutoryDeductionRule`
to a specific chart-of-accounts payable entry per rule, and
fabricating one risked an incorrect real accounting record.

```
BACKEND GAP:
Endpoint: e.g. POST /v1/wfm/payroll-runs/<id>/post-to-finance
Expected behavior: a real, dedicated posting flow that knows each
  StatutoryDeductionRule's own correct payable account (a new,
  real mapping field on that model) and posts the full, correct
  three-way split (expense, net payable, each real deduction's own
  payable) in one real, balanced entry
Why frontend requires it: without this real mapping, a UI can only
  ever post the simplified gross-only version this batch built, or
  ask the user to somehow account for deductions manually (worse)
```

**Payroll's "Bank export" is a real, generic CSV** (name, bank
reference, net pay), not a bank-specific file format (e.g., Nigeria's
NIBSS single-credit format). This batch's own brief says "where
existing architecture supports it" — a generic CSV of the real data
that exists is what this backend honestly supports; a bank-specific
format needs real, bank-specific field mapping this batch doesn't
have.

**Subcontractor Dashboard shows no tenant-wide aggregate for
claims, certificates, compliance, or performance.** None of these has
a real tenant-wide list endpoint (only per-agreement or
per-subcontractor lists exist) — fetching every agreement's own data
just to sum one dashboard number would be a real N+1 query pattern,
which this batch's own established discipline (from the earlier
Global Search and entity-picker work) deliberately avoids.

```
BACKEND GAP:
Endpoint: e.g. GET /v1/sub/claims/pending-count,
  GET /v1/sub/compliance-documents/expiring (mirroring HSE's own
  real list_expiring_certifications pattern)
Why frontend requires it: without a real, tenant-scoped aggregation
  endpoint, a dashboard-level count can only be computed by fetching
  every agreement's own data individually -- not a real, scalable
  pattern
```

## Integration points — what's real, what isn't

This batch's brief lists 9 real cross-module integration points. Here
is the honest state of each, checked directly rather than assumed:

- **WFM → FIN**: real (Post to Finance, simplified as documented
  above).
- **WFM → PC**: the real backend function
  (`services.allocate_labor_cost`, exposed via
  `GET /wfm/labor-cost-allocation`) already exists and was found
  while writing this document — no frontend UI was built to surface
  it this batch.
- **WFM → EXE**: not addressed. No real integration point was found
  or built between WFM and Module 6 (Site Execution/diaries) in this
  batch.
- **SUB → PRC**: not addressed directly, though `SubcontractAgreement`
  already links to a real `contract_id` (Module 8), which is itself
  procurement-adjacent; no direct SUB↔PRC data flow was built.
- **SUB → EST**: real, already in place before this batch —
  `SubcontractScopeItem.boq_item_id` links a real scope item to a
  real BOQ item from Module 5 (Estimating).
- **SUB → EXE**: not addressed. No real integration point was found
  or built.
- **SUB → BIL**: not addressed as a direct integration — `SUB`'s own
  `PaymentCertificate` is a real, complete billing concept in its own
  right (Module 12's own certification flow), but nothing connects it
  to Module 10 (Billing)'s own `ProgressCertificate`.
- **SUB → FIN**: not addressed — no equivalent to WFM's own "Post to
  Finance" action was built for subcontractor payment certificates.
- **SUB → PC**: not addressed. No real integration point was found or
  built between SUB and Module 19 (Project Control/EVM).

```
BACKEND GAP (shared shape for every unaddressed integration above):
Endpoint: varies per integration -- each would need its own real,
  specific data flow (e.g. SUB -> FIN needs the equivalent of
  WFM's post-manual-exception flow, scoped to a real payment
  certificate's own net_payable)
Why not built: this batch's own scope, given its size, was
  prioritized toward the explicitly-required screens and actions
  first; cross-module posting flows for SUB specifically were not
  reached
```

## What was deliberately not built as a fake feature

No fabricated leave entitlement number, no invented "approved"
payroll status, no unbalanced or deductions-fabricated finance
posting, no bank-specific export format without real field mapping,
no tenant-wide SUB aggregate requiring N+1 fetching, no fake "Approve
Attendance" workflow without a real status to represent it. Every
omission above is either left out of the UI entirely, or documented
here with the exact real endpoint/migration that would close it.
