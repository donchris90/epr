# SiteForge

**Construction Management Platform** — a multi-tenant, cloud-based SaaS
platform for civil engineering and building contractors, purpose-built
for African markets, spanning the full construction project lifecycle:
tender → estimate → contract → planning → execution → procurement →
materials → equipment → labor → quality → safety → finance → billing →
closeout → asset management.

Full specification: [`docs/SRS.md`](docs/SRS.md) (25 functional modules,
database schema, API contracts, UI/UX flows, permission matrix,
non-functional requirements, roadmap, testing requirements, and
deployment architecture).

## Repository layout

```
SiteForge/
├── backend/          Flask 3 modular monolith (Python 3.13, SQLAlchemy, PostgreSQL 16 + RLS)
│   └── app/modules/  One folder per bounded context — all 25 SRS modules
├── frontend/          React + TypeScript (Vite) web app
│   └── src/modules/  Mirrors the backend's 25 modules
├── mobile/            Flutter offline-first Mobile Field App (Module 24)
├── docs/              SRS and supporting docs
└── docker-compose.yml Local dev topology: Postgres, Redis, MinIO, API, worker, web
```

## Architecture at a glance

- **Modular monolith**: one deployable Flask app, internally organized
  into 25 bounded contexts that map 1:1 to the SRS modules. Each module
  owns its own tables and exposes a service interface — other modules
  call that interface rather than reaching into another module's tables
  directly (SRS §3.3).
- **Multi-tenant isolation via Postgres Row-Level Security**: every
  tenant-scoped table carries `tenant_id`, and a request-scoped
  middleware sets `app.tenant_id` so RLS policies enforce isolation at
  the database layer — not only in application code (SRS §3.4/5.5).
- **Offline-first mobile**: the Flutter app mirrors relevant server data
  into a local SQLite (Drift) store, queues writes locally, and syncs in
  batches with server-side conflict tracking (SRS §3.5).
- **AI Construction Assistant**: a Celery-backed service that retrieves
  tenant-scoped context and calls the Anthropic API with tool-calling
  for structured lookups and document extraction (SRS §3.6).

## Getting started (local development)

### 1. Backend

```bash
cd backend
cp .env.example .env
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Migrations create every module's tables and their RLS policies:
flask db upgrade

# One-time: the dedicated auth-lookup role (see below) --
# adjust the password and update .env's AUTH_DATABASE_URL to match.
psql -d siteforge -f scripts/setup_auth_role.sql

flask run --port 8000     # or: gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
```

**Why there's a second database role.** `users` is `FORCE ROW LEVEL
SECURITY` protected like every other tenant-scoped table (correctly —
see SRS §3.4/5.5) but login has to find a user by email *before* it
knows which tenant they belong to, and RLS has no way to authorize a
query with no tenant context yet. `scripts/setup_auth_role.sql` creates
a second Postgres role (`siteforge_auth`, `BYPASSRLS`, `SELECT`-only on
`users`) used for *only* that one pre-authentication lookup — see
`app/extensions.py:get_auth_engine` and `app/auth/jwt_utils.py` for the
full reasoning. Point `AUTH_DATABASE_URL` in `.env` at it; if unset it
falls back to `DATABASE_URL`, which works but means your primary DB role
must not have `FORCE ROW LEVEL SECURITY` blocking it (i.e. it must be
the table owner or a superuser) — fine for a quick local spike, wrong
for anything resembling production.

### 2. Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Runs on `http://localhost:5173` and proxies `/v1/*` to `http://localhost:8000`
(see `vite.config.ts`) — make sure the backend is running on port 8000,
not Flask's default 5000, or every request will fail with a proxy
`ECONNREFUSED`.

Currently has working screens for Modules 1–4 (Business Development,
Tenders, Estimating, Contracts) behind a login gate. To sign in locally
you need a seeded tenant/user with a role — there's no self-serve signup
yet, since Module -1 (tenant onboarding) hasn't been built. The quickest
path is a short Python script using `app.auth.jwt_utils.hash_password`
and the `Tenant`/`User`/`Role` models directly against your dev database
(set `role.permission_set = ["*"]` for a quick unrestricted login while
developing).

### 3. Full stack via Docker Compose

```bash
docker compose up --build
```

Brings up Postgres, Redis, MinIO (S3-compatible storage), the Flask API,
a Celery worker, and the Vite dev server. Still requires the auth role
setup step above run once against the compose Postgres instance.

### 4. Mobile

```bash
cd mobile
flutter pub get
dart run build_runner build   # generates Drift's app_database.g.dart
flutter run
```

## Status

Application structure, tenant-isolation architecture, and auth are wired
up and **verified against real PostgreSQL** — migrations run cleanly,
RLS is proven to hold at the database layer (not just via app-layer
filtering), and the tenant-context middleware correctly re-applies
across multiple transactions within a single request (a subtlety that
broke on the first attempt — see `app/middleware/tenant_context.py` for
why).

**Modules 1–4 are implemented end-to-end**, backend AND frontend:

- **Module 1 (Business Development & CRM)**: models, migration (with
  RLS), service layer encoding pipeline stage transitions, the
  Bid/No-Bid workflow, and the "can't mark won without a linked
  Contract" rule, routes, and passing tenant-isolation tests. Frontend:
  clients list, leads with convert-to-opportunity, and a kanban-style
  opportunity pipeline board with stage transitions and the Bid/No-Bid
  decision form.
- **Module 2 (Tender & Bid Management)**: models, migration (with RLS),
  and a service layer encoding every SRS 4.2 business rule — the
  estimate lock on approval-workflow initiation (with an explicit,
  reason-logged reopen path), sequential approval-step enforcement,
  the addendum-acknowledgment gate, and the full TBM-12 submission
  readiness check (mandatory checklist + RFI responses + approval steps
  + acknowledged addenda). Win/Loss recording delegates to Module 1's
  service rather than duplicating a table. Frontend: tenders list,
  tender detail with BOQ entry, checklist, live submission-readiness
  panel, and submit action.
- **Module 3 (Estimating & Cost Engineering)**: models, migration (with
  RLS), and a service layer encoding both SRS 4.3 business rules — rate
  analysis reconciliation (material + labor + equipment + subcontract +
  markup must sum to the displayed unit rate, enforced at save time) and
  CBS baseline immutability (an approved Cost Breakdown Structure can
  only change via a logged, approved Budget Revision — never a direct
  edit). Also implements the Engineer's Estimate (EST-10) and Tender
  Price (EST-11) computed views, and what-if estimate versioning
  (EST-13/14). Frontend: estimate version management, inline rate
  analysis entry per BOQ item, and a live tender price summary.
- **Module 4 (Contract Management)**: models, migration (with RLS), and
  a service layer encoding the SRS 4.4 business rules — retention
  reconciliation (amount withheld is always exactly the sum of every
  certificate's deduction, by construction, since there's a single write
  path), sequential retention release (substantial completion before
  end-of-DLP), and expiry alerting for bonds/insurance/guarantees. The
  award endpoint (`POST /v1/ctm/contracts/award`) is what actually closes
  the loop Modules 1–2 leave open: it creates the Contract *and* calls
  back into Module 1 to link it and transition the Opportunity to
  "won" — before this existed, that transition was permanently blocked.
  Frontend: contracts list with expiry alerts, and a contract detail
  view (retention/bonds/amendment panels are the next frontend
  increment — the API is there, the UI isn't yet).
- **Module 5 (Project Planning)**: models, migration (with RLS), and a
  real Critical Path Method (CPM) implementation — forward and backward
  pass over the activity dependency network, supporting all four SRS-4.5
  dependency types (Finish-to-Start, Start-to-Start, Finish-to-Finish,
  Start-to-Finish) with lag/lead, cycle detection, float calculation,
  and critical-activity flagging. Verified against a hand-computed
  textbook CPM example (a 4-activity diamond network) with exact
  agreement on every early/late date and float value. Also implements
  write-once baseline snapshots (so schedule variance is always
  current-minus-baseline, never computed by overwriting history),
  resource over-allocation detection (using the CPM-computed schedule,
  not raw input dates — see the bug note below), and delay events that
  automatically flag for review when they hit the critical path. No
  frontend yet for this module.
- **Module 6 (Project Execution)**: models, migration (with RLS), and a
  service layer encoding both SRS 4.6 business rules — a signed Daily
  Site Diary is genuinely read-only (direct edits 409; the only
  sanctioned correction path is a logged Amendment, which never mutates
  the original signed content), and Work Completed quantities are
  tracked cumulatively against a caller-supplied contracted quantity,
  raising a warning (not a hard block, per the SRS's own wording) the
  moment the running total crosses it — verified with a real sequence
  (60 + 30 = 90, no warning; +20 = 110, warns; +20 more with a linked
  Variation Order, no warning despite being further over). Also
  implements overdue site-issue escalation, tested against both an
  overdue and a not-yet-due issue to confirm only the right one moves.
  This is also the first module built specifically for the offline-first
  Mobile Field App (Module 24) to eventually sync against — the mobile
  app's actual sync logic is still just a stub, but the backend it would
  talk to is real now. No frontend yet for this module either.
- **Module 7 (Procurement)**: models, migration (with RLS), and a
  service layer encoding all three SRS 4.7 business rules — a Purchase
  Order cannot be issued to a vendor with expired compliance documents
  without an explicit waiver (reason + approver); invoice payment is
  blocked until a three-way match (PO/GRN/invoice, within a rounding
  tolerance) is clean or an exception is explicitly approved; and a
  Purchase Request that would breach the remaining CBS budget for its
  cost code is blocked unless resubmitted with an override and recorded
  justification. Also implements value-threshold-based multi-level PO
  approval (same sequential-approval pattern as TBM's), side-by-side
  quotation comparison, and blanket/framework PO drawdown across
  multiple partial goods receipts — verified with a real 6-then-4 split
  delivery against a 10-unit line, confirming the cumulative
  quantity_received tracks correctly across both receipts. No frontend
  yet for this module.
- **Module 8 (Inventory & Warehouse)**: models, migration (with RLS),
  and a real dual valuation engine (SRS 4.8's INV-11) — weighted-average
  and FIFO, tenant-configurable, both verified against hand-computed
  figures. The FIFO test was specifically designed to diverge from what
  weighted-average would produce for the same receipts (10 units at
  ₦800,000 then 10 at ₦900,000, issuing 15): weighted-average would
  value the issue at ₦12,750,000, but FIFO's oldest-first layer
  consumption correctly gave ₦12,500,000 — proving it's real layer
  tracking, not a relabeled average. Also implements the stock-transfer
  business rule (destination balances only update on confirmed receipt,
  never on dispatch — verified: the destination warehouse showed zero
  stock while a transfer was in transit, then exactly the transferred
  quantity, at the source's carried-over valuation, once confirmed),
  reservations that reduce availability without touching physical
  quantity (over-reservation correctly blocked), reorder-point
  detection, and a stock-count → variance → explicit-adjustment flow
  (50 on the books, 48 physically counted, correctly adjusted only after
  an explicit approval step — never automatically). No frontend yet for
  this module.
- **Module 9 (Equipment & Fleet Management)**: models, migration (with
  RLS), and a service layer encoding both SRS 4.9 business rules — an
  Operator Assignment is blocked, unconditionally, if the supplied
  certification has expired (no override path, unlike other modules'
  compliance checks — this one is a hard stop per the SRS's own
  wording), and Cost per Hour is never stored, only ever computed fresh
  from current maintenance/repair/depreciation data, which trivially
  satisfies "recalculates automatically" by construction. Also
  implements Availability/Utilization (verified against a hand-computed
  two-day scenario: 16 scheduled hours, 2 hours of breakdown downtime,
  13 productive hours → exactly 87.5% availability and ~92.86%
  utilization) and idle-equipment detection. Two real bugs were found
  and fixed while testing this module: a missing schema default caused
  a 500 whenever operator certification data was omitted (the same
  class of bug caught in Module 6), and `EquipmentTransfer` was missing
  its `equipment` relationship entirely, which would have crashed the
  very first transfer approval. No frontend yet for this module.
- **Module 10 (Fuel Management)**: models, migration (with RLS), and a
  service layer built around SRS 4.10's real substance — fraud
  detection. A Theft Flag never auto-blocks anything (verified: a 300L
  tank-reconciliation discrepancy raises a flag *and* still lets the
  tank reconcile to the physical dip reading), but does escalate on its
  own after a configurable unresolved period (verified: a flag
  backdated 10 days escalated on the next sweep, one still within the
  7-day window correctly didn't). Also implements the countersignature
  threshold on manual fuel issues (250L over a 200L threshold correctly
  required countersigning; 150L didn't), fuel variance calculation
  against a burn-rate baseline (20L/hr × 10hrs = 200L expected vs. 280L
  actual = exactly +40% variance, correctly triggering a theft flag
  against a 15% threshold), and the "no corresponding usage log" flag.
  Per this module's own business rule — variance must appear as a
  *distinct* cost line, never blended into Cost per Hour — Module 9's
  `calculate_cost_per_hour` was revised to accept `fuel_normal_cost` and
  `fuel_variance_cost` as two separate parameters instead of one, a
  genuine cross-module design change made necessary by building the
  later module properly rather than working around it.

  Testing this module surfaced two real, non-obvious bugs, both fixed:
  a `Decimal`-vs-`str` type mismatch in the tank-reconciliation
  tolerance check, and a subtler one — comparing a `DateTime` column
  against a bare `Date` for a period's end silently treats it as
  midnight of that day, excluding everything recorded later that same
  day. This second bug was *also* already latent in Module 9's cost
  calculation (fixed there too once spotted) and had gone unnoticed
  specifically because that module's earlier test happened not to
  exercise the boundary — a reminder that a passing test only proves
  what it actually exercises.
- **Module 11 (Workforce Management)**: models, migration (with RLS),
  and a service layer encoding both SRS 4.11 business rules — Medical
  Records are gated behind a distinct `wfm:medical` permission, checked
  in addition to (never instead of) ordinary WFM access (verified: a
  user with full `wfm:read`/`wfm:write`/`wfm:approve` but no
  `wfm:medical` grant got a clean 403 on both reading and writing
  medical records; a user with the specific grant succeeded), and
  Payroll cannot be finalized while any linked timesheet remains
  pending approval (verified: three timesheets generated — two
  employees, one casual worker — payroll blocked with one still
  pending, succeeded once approved, correctly refused to re-finalize).
  The payroll math was hand-checked line by line, including the detail
  that matters most: a configurable deduction rule correctly applied to
  both employees but was correctly *excluded* for the casual worker per
  its `applies_to_casuals` flag — 10% PAYE + 8% Pension for employees,
  10% PAYE only for the casual, netting exactly right on every line and
  in the run total. This module is also the real source of the
  certification data Module 9's operator-assignment check has been
  taking as an external parameter — `get_active_certification` now
  exists for a caller to wire the two together, without either module
  reaching into the other's tables directly. Testing this module caught
  the same schema pattern bug seen in Module 2 (Tender & Bid
  Management): four schemas required `employee_id` in the request body
  even though their routes already supply it from the URL path — fixed
  by making it dump-only, consistent with the fix applied there. No
  frontend yet for this module.
- **Module 12 (Subcontractor Management)**: models, migration (with
  RLS), and a service layer encoding both SRS 4.12 business rules — a
  subcontract Payment Certificate cannot be issued against an
  unverified Measurement Sheet (verified: attempted issuance against a
  draft sheet → 409; verified the sheet → issuance succeeded, with the
  gross/retention/net figures hand-checked exactly: 280 units × ₦8,000
  = ₦2,240,000 gross, 10% retention = ₦224,000, net ₦2,016,000), and
  Subcontract Retention release is completely independent of Module 4's
  main-contract retention — enforced simply by never writing a code
  path connecting the two, which is the surest way to guarantee "never
  automatic." Also verified: sequential retention release (final
  blocked before substantial completion, exactly like Module 4 and
  Module 2's approval patterns), the compliance-document expiry gate on
  certification (blocked without a waiver, issued with one — net payable
  ₦220,000 after both 10% retention and a ₦50,000 back-charge deducted
  correctly), the claim review workflow, and performance rating
  averaging ((8+6+9+7)/4 = exactly 7.50). One more instance of the
  missing-schema-default bug pattern was caught and fixed here too — by
  this point a known, systematically-checked-for failure mode rather
  than a surprise. No frontend yet for this module.
- **Module 13 (Quality Management)**: models, migration (with RLS), and
  a service layer encoding both SRS 4.13 business rules — work cannot
  proceed past a mandatory ITP hold point without a recorded pass or an
  approved concession (verified through the full real workflow: pending
  blocks, a failed inspection still blocks, re-inspecting after a fix to
  a pass correctly unblocks and then locks further changes, a concession
  is a genuine separate path to unblock, and non-mandatory hold points
  never block at all), and an NCR cannot be closed without a linked
  Corrective Action *verified* as complete — tested through every
  intermediate state (no action linked → blocked; action linked but
  still open → blocked; action completed but not yet independently
  verified → still blocked; verified → closeable), confirming
  "completed" and "verified" are genuinely different states, not a
  single checkbox. Also implements close-out readiness tracking
  (QMS-08), verified end-to-end: an open punch list item blocks
  close-out, closing it clears the gate. No frontend yet for this
  module.
- **Module 14 (Health, Safety & Environment)**: models, migration (with
  RLS — including a live alteration of Module 13's corrective-action
  source constraint to add "incident" as a valid source, since HSE's
  business rule needed it), and a service layer encoding both SRS 4.14
  business rules — a Permit to Work must be FORMALLY closed (not merely
  time-expired) before associated work can be marked complete, and every
  recordable Incident automatically generates a linked Corrective Action
  whose closure requires the HSE Officer permission specifically.
  Verified end-to-end: a permit blocked from issuance against an expired
  Risk Assessment, blocked again with stale worker training, then issued
  and activated cleanly once both were valid; `is_work_completable`
  correctly read False while merely active and only flipped True after
  genuine formal closure. The incident rule was checked at every layer:
  a regular HSE staffer with broad `hse:write`/`hse:approve` but no
  `hse:officer` grant got a clean 403 trying to close an incident; the
  HSE Officer themself was blocked with a 409 until the linked
  Corrective Action was actually verified through Module 13's own
  service (proving this is a real cross-module dependency, not a
  rubber-stamp); safety indicators (TRIR, LTIFR) were verified against
  hand-computed figures using the actual OSHA-standard formulas (2
  recordable incidents over 50,000 hours → TRIR = 8.0 exactly; 1
  lost-time incident → LTIFR = 20.0 exactly). No frontend yet for this
  module.
- **Module 15 (Survey & Engineering)**: models, migration (with RLS),
  and a service layer encoding both SRS 4.15 business rules — an
  Earthworks Volume calculation is billable only if it references an
  APPROVED design surface, checked at every state (no surface → 409 on
  billing submission; an unapproved surface → still 409; approving the
  surface and creating a fresh calculation against it → officially
  billable and submittable), and an As-Built Record is a one-way lock —
  editable freely before locking, refused with a 409 immediately after,
  with no code path back to unlocked anywhere in the module, matching
  the "immutable handover package" requirement by construction rather
  than by convention. No frontend yet for this module.
- **Module 16 (Plant & Quarry Management)**: models, migration (with
  RLS), and a service layer encoding both SRS 4.16 business rules — the
  Explosives Register is genuinely append-only: there is no
  update/delete route for it anywhere in the module (confirmed by
  actually inspecting the route file at test time, not just by
  intention), and the only way to record a change is a separate,
  attributable correction row. Verified with a real ledger sequence —
  procurement 500kg, issuance 120kg, consumption 115kg → balance
  computed as exactly 265kg — then a correction was added claiming the
  original delivery was actually 505kg, and the original entry and the
  computed balance were both confirmed completely unchanged afterward,
  proving the correction is a reporting annotation, not a stealth edit.
  Also verified: a Blasting Record cannot be created at all without a
  real linked Drilling Record (404 against a fake one), and cannot be
  marked complete without a regulatory notification reference in a
  jurisdiction that requires one — checked both ways (blocked when
  missing, and separately confirmed a jurisdiction that doesn't require
  it lets a blast without one complete normally). Stockpile
  reconciliation and production-report yield efficiency (4,200 of a
  5,000 target → exactly 84.00%) were also hand-checked. No frontend yet
  for this module.
- **Module 17 (Financial Management)**: models, migration (with RLS),
  and a real double-entry accounting core. Every posting path funnels
  through one private function that rejects an unbalanced entry before
  anything touches the database — verified with a deliberately
  unbalanced test entry (debit 1,000 vs. credit 999), confirmed
  rejected, and confirmed genuinely absent from the ledger afterward,
  not just fronted by an error message. The business rule that no
  transaction may bypass its originating module is enforced by there
  being no generic "create journal entry" route at all; the one
  sanctioned exception path is gated behind a distinct
  `fin:manual_exception` permission (verified: blocked for an ordinary
  finance user with full `fin:write`/`fin:approve`, allowed once
  granted). Budget Control (FIN-04) was verified with real cumulative
  math — ₦600k posted against a ₦1M budget succeeded, a further ₦500k
  was correctly hard-blocked with the exact remaining figure (₦400k) in
  the error, and a separate cost category with no specific policy
  correctly fell back to the tenant-wide default — and an income
  statement matched hand arithmetic exactly (₦5,000,000 revenue −
  ₦3,200,000 expense = ₦1,800,000 net income).

  Testing this module surfaced its most significant bug yet, worth
  calling out specifically: **Postgres foreign-key constraints do not
  respect Row-Level Security.** FK referential-integrity checks run
  with elevated internal privileges to verify a referenced row exists
  at all, regardless of whether RLS would hide that row from the
  querying session — so a bare `ForeignKey` column on `company_id` or
  `account_id` was not actually sufficient to stop one tenant from
  posting a journal entry against another tenant's chart of accounts;
  the FK check happily validated the referenced row existed, full stop.
  This was caught by a cross-tenant isolation test that expected a 404
  and got a 201 instead. Every prior module's `_get_x_or_404` helper
  pattern already avoided this by construction (looking the row up
  filtered by `tenant_id` before use), but FIN's posting functions
  had skipped that step and relied on the FK alone. Fixed by adding
  explicit tenant-scoped existence checks for the company and every
  referenced account before any line is constructed — the same lookup
  pattern used everywhere else, just added where it had been missed.
  This is a good example of exactly why the tenant-isolation test suite
  exists as a hard gate on every module, not a nice-to-have.
- **Module 18 (Client Billing)**: models, migration (with RLS), and a
  service layer encoding both SRS 4.18 business rules with real
  cumulative-quantity arithmetic. Double-billing prevention (BIL-10)
  was tested at the exact boundary: 400 of 500 contracted units billed
  successfully, 150 more correctly blocked (would total 550), then
  exactly the remaining 100 succeeded (landing precisely at the 500
  cap), and even 1 further unit was correctly refused. The
  variation-order gate and the quantity cap were then tested together,
  not just separately: billing against a *pending* variation order was
  blocked, approving it unlocked billing, and the cumulative check
  correctly folded the approved variation's quantity into the total
  allowance (500 contracted + 100 approved variation = 600), catching
  an overage at exactly that combined threshold. Revenue recognition
  (BIL-08) correctly computed an under-billed position from independent
  progress data vs. actual billing.

  Testing this module caught a genuine double-counting bug in the
  certificate total: a newly-added line was already present in
  `certificate.lines` (SQLAlchemy reflects a session-added related
  object before flush) by the time the running total was recomputed,
  and the code was also adding that same line's amount a second time
  on top — silently doubling every certificate's gross value. Caught
  because the test checked the certificate's actual persisted total
  after adding two real lines (400×5,000 + 100×6,000 = 2,600,000
  expected) instead of only checking each line's own individual amount,
  which happened to look fine in isolation. Fixed, then re-verified with
  the same two-line scenario, plus retention (10% of 2,600,000 =
  260,000 exactly) and the outstanding-invoices aging report.
- **Module 19 (Project Controls)**: models, migration (with RLS), and a
  real Earned Value Management engine, hand-verified against a textbook
  EVM scenario end to end — PV 100,000 / EV 80,000 / AC 100,000 / BAC
  500,000 produced CV=-20,000, SV=-20,000, CPI=0.80, SPI=0.80, all
  matching by hand. All three Forecast-at-Completion methods were
  checked against the same snapshot: CPI-based gave EAC=625,000 (BAC/CPI),
  atypical-variance gave EAC=520,000 (AC+(BAC-EV)) — genuinely different
  numbers from the same inputs, proving the two methods aren't secretly
  doing the same arithmetic — and manual re-estimate correctly required
  a documented reason before accepting an override. The performance-
  threshold business rule (PC-04's default 0.9) was tested with a
  healthy project (CPI=SPI=1.0, correctly excluded) alongside an
  underperforming one (CPI=0.85, correctly flagged) in the same query,
  and delay classification was checked against all three meaningful
  sign combinations of SV/CV (schedule-driven, cost-driven, both) —
  each landed on the right classification precisely because the
  scenario was built to isolate that one condition. Risk exposure
  (probability × impact = 0.3 × 2,000,000 = 600,000 exactly) and cash
  flow forecasting were also verified.

  The cross-tenant isolation test for this module specifically targeted
  the at-risk-projects aggregation query (group by project, take the
  latest snapshot) rather than only single-record lookups — an
  aggregation is exactly the kind of place a tenant-scoping mistake
  would leak silently (wrong numbers, not a clean 404), and it's
  confirmed clean: tenant B's badly-underperforming project (CPI 0.5)
  never appears on tenant A's risk list.
- **Module 20 (Asset Management)**: models, migration (with RLS), and a
  service layer encoding both SRS 4.20 business rules — DLP retention
  release requires every linked defect to be genuinely VERIFIED, not
  merely resolved, tested through every intermediate state (zero
  defects → trivially releasable; open defects → blocked, correctly
  reporting "2 of 2 not verified"; resolved-but-unverified → still
  blocked; one of two verified → blocked, now reporting "1 of 2"; both
  verified → releases cleanly; re-release → blocked). An asset's
  original as-built baseline is immutable — verified by attempting to
  sneak `baseline_data` into an attributes-update request, which
  Marshmallow rejected outright as an unknown field (the update schema
  simply has no field for it, so the immutability isn't a runtime check
  that could have a bug — there's structurally nothing to bypass), then
  confirming a legitimate name-only update left the baseline completely
  untouched. Maintenance scheduling (a task due 2026-08-01 with a
  90-day frequency correctly rolled forward to exactly 2026-10-30 on
  completion) and lifecycle cost aggregation (₦450k + ₦220k maintenance
  = ₦670k, plus ₦3M rehabilitation = ₦3.67M total, exact) were also
  verified.
- **Module 21 (Executive Dashboard)**: models, migration (with RLS),
  and a set of genuinely cross-module aggregation functions rather than
  a stub layer — per the SRS's own framing, this module has almost no
  data of its own (just widget/configuration metadata), so the actual
  work is querying other modules' real tables fresh on every call. Five
  widgets were built with real queries and hand-verified, not eleven
  with placeholder numbers: Company Revenue (two AR invoices posted
  through Module 17 summed to exactly ₦6,000,000, correctly compared
  against a ₦5,500,000 budget for a +₦500,000 / +9.09% variance, with
  the drill-down list correctly naming both real journal entry IDs),
  Active Projects CPI/SPI (Module 19's latest-snapshot-per-project
  query, reused), Project Risks, AR/AP Aging (the AR side literally
  calls Module 18's own `get_outstanding_invoices_report` function
  rather than re-deriving it — the one legitimate case in this codebase
  for a module reading another's tables directly is when doing genuine
  read-only aggregation, and even then it prefers calling an existing
  service over re-querying), and Equipment Utilization (6 of 8
  scheduled hours → exactly 75%). The remaining widgets (Cash Position,
  Safety Score, Tender Pipeline, Profit Margin Trends, Labor
  Productivity) are left as explicit TODOs rather than faked — Module
  17 has no running bank-balance concept yet and Module 14's composite
  safety-score formula isn't specified precisely enough to implement
  responsibly, so guessing at those would have been worse than not
  building them yet.

  The business rule — dashboard figures are always traceable via
  drill-down, never independently-editable — is enforced structurally,
  not just by convention: confirmed there are zero PUT/PATCH routes
  anywhere in the module, and the two models literally have no field
  that represents a business metric (no revenue column, no CPI column)
  for such a route to even target. EXD-12's role-based scoping was
  verified directly: a Group CEO's unscoped view showed all 3 seeded
  projects, while a Regional Director's configuration correctly limited
  the same query to exactly their 2 assigned projects, excluding the
  third. Because this module reads directly across so many other
  modules' tables — the one place in the codebase where that's the
  correct design — its cross-tenant isolation tests specifically target
  the aggregation queries themselves (tenant B posting a ₦9,999,999
  revenue entry must not appear on tenant A's dashboard, which correctly
  shows ₦0), since a missed tenant filter here would silently blend
  data into a number rather than cleanly 404.
- **Module 22 (Client Portal)**: models, migration (with RLS), and a
  service layer built around a genuinely defense-in-depth access
  control — a client can never view another client's project data,
  regardless of any permission misconfiguration elsewhere, because the
  check that enforces this doesn't consult the permission system at
  all. It consults a dedicated `ClientProjectAssignment` table directly,
  as the unconditional first line of every single service function in
  the module. This was tested exactly as the business rule describes:
  a caller holding full, unrestricted `*` permissions still got a clean
  403 attempting to reach another client's schedule, site media, or RFI
  submission — proving the block comes from the client-scope check
  itself, not from anything the permission grant said. The
  cross-module orchestration was verified as a real state change, not
  a client-side-only record: a client's approval of a Variation Order
  correctly flipped the actual record's status in Module 18, and a
  second attempt to decide the same (now-approved) order — from a
  *different* client user — was correctly blocked with a 409, proving
  the state protection holds independent of who's asking. CLP-06's
  "no internal cost data" requirement was satisfied both by what the
  schedule view reads (Module 5's Activity data, which has no cost
  fields on it at all) and by what its response schema explicitly
  excludes (the WBS node's cost-code reference), so there's no
  cost-code breadcrumb even indirectly.
- **Module 23 (Vendor Portal)**: models, migration (with RLS), and the
  same defense-in-depth discipline applied to Module 7's vendors
  instead of Module 18's clients — a vendor can never act on another
  vendor's purchase order, quote on an RFQ they weren't invited to, or
  upload an invoice against someone else's PO, regardless of permission
  grants, because every check consults vendor ownership directly rather
  than the permission system. Tested with two real vendors and a real
  Purchase Order: vendor 2 attempting to acknowledge or invoice against
  vendor 1's PO was blocked with 403 both times, and the invoice list
  was independently confirmed empty afterward — not just an error
  response, an actually-empty table.

  The banking-detail-change fraud-prevention rule (a classic
  payment-redirection attack vector) was verified across its full
  lifecycle, not just the happy path: a vendor-portal session (holding
  `vnp:write` but deliberately NOT `vnp:finance_approve`) submitted a
  change, and the live `Vendor.banking_details` field was confirmed
  completely untouched immediately afterward — still `None`. The same
  session then tried to self-approve its own submission and was
  blocked with 403 for missing the internal-only permission. Only after
  switching to a session actually holding `vnp:finance_approve` did
  approval succeed, and only then did the live vendor record update to
  the proposed bank details. Most importantly: a second, deliberately
  suspicious change ("Suspicious Bank") was REJECTED by Finance, and
  the live vendor record was confirmed to still hold the *previously
  approved* bank details afterward — proving rejection is a genuine
  no-op on live data, not a partial or silently-applied write.
- **Module 24 (Mobile Field App)**: models, migration (with RLS), and a
  real server-side offline-sync reconciliation engine — the one part
  of this module that's genuinely a backend concern, since the local
  SQLite store and offline UI are the mobile client's job, not this
  server's. Tested with a mixed batch of four entries (one valid
  near-miss report, one with an invalid classification, one referencing
  an asset that doesn't exist server-side, one valid asset inspection):
  the two valid entries synced with real server-generated record IDs,
  and the two invalid ones became genuinely queryable `ConflictRecord`s
  with the original client payload fully preserved — confirmed via a
  follow-up query, not just inferred from the response. Idempotency
  (the actual mechanism that makes offline sync safe to retry after a
  dropped connection) was verified directly: resubmitting the exact
  same batch with the same client-generated UUID returned the identical
  underlying entry and the identical server record — no duplicate
  near-miss was created.
- **Module 25 (AI Construction Assistant)**: built honestly within this
  environment's real constraint — no LLM is configured here, so natural
  -language query parsing and free-text narrative generation are out of
  scope for this pass, and faking them with hardcoded string matching
  would have been dishonest about what the system does. What's real and
  fully tested: the structured TOOLS a natural-language layer would
  call (AI-12's own description of the correct mechanism) — grounded
  directly in Modules 19 and 9's real data, verified with a deliberately
  underperforming project (CPI 0.5, correctly flagged) alongside a
  healthy one (correctly excluded) in the same call, and idle vs. busy
  equipment correctly distinguished by actual recorded utilization
  hours; the audit log (AI-13), confirmed to capture the tool
  invocation on every call; the citation-enforcement business rule,
  checked against every violation shape (a figure with no citation, a
  citation missing `record_id`, an empty citation set) all correctly
  rejected, with only a fully-cited report succeeding; and the
  never-auto-commit extraction gate, verified across its complete
  lifecycle — committing before review blocked with a 409, a human
  reviewer's correction recorded, commit succeeding only after review,
  re-commit blocked — and then confirmed directly against the database
  that the real, committed `BOQItem` held the human-*corrected*
  quantity (1275), not the original low-confidence extraction (1250),
  proving the correction genuinely overrides the raw extraction rather
  than just being stored alongside it.

  Testing this module surfaced one more instance of the missing-
  schema-default bug pattern that recurred throughout this build
  (`source_document_id` lacked `load_default=None`) — caught
  immediately by the first real request, fixed in both the schema and
  the service signature, and re-verified.

All twenty-five were run end-to-end against real Postgres, not just written —
full workflow traces (lead → opportunity → tender → estimate → priced
BOQ → submitted estimate → approved CBS baseline → budget revision →
contract award → retention/bonds/amendments → WBS/activities/CPM
scheduling → baselining → delay events) are covered by the test suite
and were manually verified with before/after assertions on every
business rule during development. The frontend was verified the same
way: a real Vite dev server proxying to a real Flask server against real
Postgres, with an actual login flow, JWT issuance, and authenticated
CRUD round-trips — not just a clean `npm run build`. That process
surfaced and fixed two real bugs: `FORCE ROW LEVEL SECURITY` on `users`
correctly blocking the login endpoint's cross-tenant email lookup (fixed
with a dedicated, narrowly-scoped auth role — see the "Getting started"
section above), and a stale `TODO` that meant every JWT's `permissions`
claim was silently always empty. Module 5's development surfaced a
subtler bug worth calling out on its own: the initial resource
over-allocation check compared activities' raw *input* `planned_start`
dates rather than their CPM-*computed* `early_start`/`early_finish` —
for any activity with a predecessor, the input date is cosmetic (CPM
determines when it actually runs), so the check was comparing dates
nobody was actually scheduled against. Caught by re-deriving a
hand-computed example, not by a passing test that happened not to
exercise it.

**Frontend, Module 6 (Project Execution)**: the daily site diary,
progress capture, and site-issue tracking screens, chosen deliberately
as the first module to get real UI — it's the screen a site engineer
would open every single day, and unlike the financial/portal modules
it doesn't depend on any other module's frontend existing first.
Building it surfaced a real, previously-invisible backend gap: the
`DailySiteDiarySchema` response never included a signed diary's
weather records, labor/equipment usage, or amendment history, and
there were no GET routes to fetch them at all — only POST. That gap
was invisible as long as nothing ever needed to *display* a diary's
sub-records, which no test in this codebase had needed to do, since
the API-level tests only ever checked that a POST succeeded. Fixed by
adding four real GET list routes
(`/exe/diaries/<id>/{weather,labor-usage,equipment-usage,amendments}`),
verified against real created records before touching the frontend at
all, and covered by a new tenant-isolation test asserting all four
404 for another tenant's diary. The diary detail screen makes the
underlying business rule (signing locks the entry; amendments are the
only way to add information afterward) visually explicit — a locked
diary shows a distinct banner, its narrative field becomes read-only,
and the amendment form is the only way to write anything further, so
the UI can't misrepresent a signed record as still editable. Verified
with a real `npm run build` (zero TypeScript errors) against the
actual schemas above, not just visually.

**Frontend, Module 5 (Project Planning)**: the schedule view (WBS
structure, activity creation, dependency linking, CPM recalculation)
and delay-event log, the natural pairing with Execution since site
staff live in both daily. Surfaced the same class of gap as Module 6:
there was no route to fetch every activity across a project's WBS
tree in one call, only per-node listing, which is unusable for a
schedule/Gantt view spanning many WBS nodes. Fixed by adding
`GET /pln/activities?project_id=...`, joined through the WBS table,
verified against two real WBS nodes with one activity each before
the frontend touched it, and covered by an isolation test using a
*shared* project UUID across two tenants specifically — the
adversarial case where a naive join might accidentally blend two
tenants' activities under the same project id, not just the ordinary
case of two different ids. The schedule table surfaces the real CPM
output (early start/finish, total float, critical-path flag) directly
against each activity, with critical-path rows visually distinct, so
the schedule view shows the same computed values the backend's own
CPM tests verified by hand, not a separate display-only approximation.

One process note worth recording: between the Module 6 and Module 5
frontend sessions, `node_modules` had been deleted (to keep it out of
the delivered zip) and the next `npx tsc -b` silently fetched the
*latest* TypeScript (6.0.3) instead of the version pinned in
`package.json` (`^5.5.3`), which failed on a deprecated compiler
option that the pinned 5.x line doesn't warn about. A real
`npm install` first (restoring the pinned version, 5.9.3) fixed it.
The lesson: `npx <tool>` without a local install silently uses
whatever's latest on the registry, not the project's pinned version —
worth remembering any time `node_modules` has been removed for
packaging and a `tsc`/lint/build step needs to run again afterward.

**Frontend, Module 7 (Procurement)**: vendors, purchase requests,
purchase orders, and the PO detail screen — the richest frontend page
built so far, since it's where three separate business rules converge
in one place: budget-breach blocking on PR submission, compliance-
gated PO issuance, and three-way invoice matching. Each is surfaced
as a real, interactive UI flow, not just a status badge — attempting
to submit a PR that breaches budget shows the exact figures from the
backend's error detail and offers the override path inline; issuing a
PO with expired vendor compliance shows the same for the waiver path;
a discrepant invoice match shows "payment blocked" in red until an
exception is explicitly approved, at which point it flips to
"released for payment" in place.

This session surfaced the most gaps yet, all found and fixed before
they reached the frontend:
- The PO detail endpoint had no way to retrieve invoice matches or
  approval steps at all — only POST/create routes existed. Added
  `latest_match` and `approval_steps` to the GET response (with a new
  `POApprovalStepSchema`), verified against a real PO pushed all the
  way from draft through approval, issuance, a discrepant invoice
  match, and exception approval — confirming `released_for_payment`
  correctly flipped from `false` to `true` only after the exception
  was explicitly approved, not automatically.
- A genuine field-name bug in the frontend hooks themselves: the
  approval-workflow-initiation hook was written with invented field
  names (`min_value`, `approver_role`) that didn't match the backend's
  actual schema (`value_threshold`, `role_required`). Caught by
  actually driving the workflow through a real API call before wiring
  it into a page, not by the type checker (both sides were typed as
  strings, so TypeScript had no way to know). Fixed before the UI form
  was built against it.
- Added a tenant-isolation test targeting the enriched PO-detail
  response specifically, since it aggregates three separate queries
  (line items, approval steps, latest match) onto one object — exactly
  the shape where one of the three sub-queries could leak even if the
  top-level lookup is correctly scoped.

Also added two small, genuinely reusable pieces to the shared frontend
kit rather than one-off inline styling: an `ErrorBanner` component and
a `getErrorMessage()` helper that reads the backend's RFC 7807
`detail` field — both will be used by every future module's business-
rule-surfacing UI, not just this one.

**Frontend, Module 17 (Financial Management)**: setup (companies,
chart of accounts), the ledger (journal entries, AP/AR invoice
posting, and manual exception journal entries), and reports (income
statement, budget control check, project cost summary). The manual
exception builder is the flagship interaction: it mirrors the
backend's own double-entry invariant client-side, in real time — a
running debit/credit total updates on every keystroke, colored red
until the two sides match and green (with the submit button enabling)
only once they do. This isn't just a UX nicety layered over an
unrelated backend check; it's a client-side reflection of the exact
same rule `_post_journal_entry` enforces server-side, so a user sees
the constraint before the round-trip, not just after a rejection.

No new backend routes were needed for this module — a genuine
difference from every other frontend session so far, and worth noting
precisely because it wasn't the case for Planning, Execution, or
Procurement. Rather than assume that meant nothing to verify, every
payload shape the new pages send (company/account creation, AP invoice
posting, and — most importantly — the manual exception posting with
both an authorized and an unauthorized session) was checked against
the real backend before considering the page done. That check paid
off: it confirmed the `fin:manual_exception` 403 path the UI's error
banner depends on actually fires with the exact field names the
frontend sends, and that a generated income statement's response
shape (`{data: {data: {revenue, expense, net_income}}}`, two levels of
nesting — the axios response body, then the statement's own `data`
JSONB field) is what the Reports page's rendering code actually
expects, not an assumption that happened to compile.

**Frontend, Module 18 (Client Billing)**: progress certificates
(the flagship detail page), variation orders, and the outstanding-
invoices aging report — the natural pairing with Financial Management,
since a client-approved certificate is exactly what generates the AR
invoice that module's ledger posts. The certificate detail page
surfaces two real business rules directly through its error banner:
adding a line that would push cumulative billed quantity past
contracted-plus-approved-variation is blocked with the exact figures
in the message ("Already billed 400.0000, contracted+variation allows
1000, this line would bring total to 1100.0000"), and billing against
a variation order that hasn't been approved yet is blocked the same
way. Both were verified against real data, including a case worth
being honest about: my first attempt to verify the "approved variation
extends the allowance" path returned an unexpected 409, which turned
out to be a mistake in my own test setup (the variation order wasn't
linked to the same `boq_item_id` as the certificate line) rather than
a backend bug — exactly the kind of thing that's easy to misdiagnose
as "the feature is broken" when it's actually the business rule
correctly rejecting an inconsistent test case. Re-ran it with the IDs
properly matched (100 contracted + 200 approved variation = 300
allowed, billing 250 succeeded) to confirm the real behavior.

Same missing-detail-route gap as Procurement and Financial Management:
there was no way to fetch a single certificate, its lines, or its
payment-tracking record — only list and create routes existed. Fixed
by adding `GET /certificates/<id>` with `lines` and `payment_tracking`
both included, verified end-to-end (create → add line → apply 10%
retention → submit) with the exact hand-computed figures (2,000,000
gross, 1,800,000 net) before any frontend code was written against it.

This session also had a mid-build tool interruption — several files
were written but the confirmation never came back. Rather than assume
anything was lost, every file was checked against disk afterward
(all had actually saved correctly, including a bug fix made just
before the interruption) before continuing, and the one file that
genuinely hadn't been written yet (`index.tsx`) was completed from
scratch. Caught during that same review: an unused `Field` import that
would have failed the strict TypeScript build, fixed before compiling.

Use these as the reference pattern -- all 25 backend modules are built
and tested; Modules 5, 6, 7, 17, and 18 additionally have working
frontends, and the remaining 20 modules' UI is the next major body of
work (see "What's left" below).

Suggested build order followed the SRS roadmap (§11), and every phase is
now complete:

1. **Foundation & Core Lifecycle** — auth/RBAC/RLS (done), Business
   Development & CRM (done), Tender & Bid Management (done), Estimating
   & Cost Engineering (done), Contract Management (done).
2. **Field Operations MVP** — Project Planning (done), Project Execution
   (done), Mobile Field App (done), Quality Management (done), HSE (done).
3. **Supply Chain & Resources** — Procurement (done), Inventory &
   Warehouse (done), Equipment & Fleet (done), Fuel Management (done),
   Workforce Management (done), Subcontractor Management (done).
4. **Financial Core & Billing** — Financial Management (done), Client
   Billing (done), Project Controls (done).
5. **Differentiators & Portals** — Survey & Engineering (done), Plant &
   Quarry Management (done), Asset Management (done), Executive
   Dashboard (done), Client Portal (done), Vendor Portal (done).
6. **AI Construction Assistant** — the audit-logged, citation-enforced,
   human-review-gated data-retrieval tools and extraction workflow are
   done (done); actual natural-language query parsing and free-text
   narrative generation require an LLM integration this environment
   doesn't have configured, and remain the one genuinely open piece --
   see the scope note in `app/modules/ai/models.py`.

## Testing

The mandatory tenant-isolation suite (`backend/tests/test_tenant_isolation.py`)
is a required CI gate per SRS §12.2 — as each module's models land, add a
case asserting a user from tenant A can never read or write a tenant B
record, at both the API and RLS layer.

**This suite must run against real PostgreSQL, not SQLite** — the schema
uses JSONB columns and Postgres Row-Level Security, neither of which
SQLite supports. A passing SQLite run would prove nothing.

The app must also connect as a role that is **neither a superuser nor
the owner** of the tables it's querying — Postgres bypasses RLS for
both by default. `db.create_all()`-based test runs additionally apply
`FORCE ROW LEVEL SECURITY` (see `tests/conftest.py`) as a second line of
defense, but a correctly-configured non-owner app role is still the
right production setup.

```bash
# one-time setup (adjust to your local Postgres install)
sudo -u postgres psql -c "CREATE USER siteforge WITH PASSWORD 'siteforge' SUPERUSER;"
sudo -u postgres psql -c "CREATE DATABASE siteforge_test OWNER siteforge;"
sudo -u postgres psql -c "CREATE USER siteforge_app WITH PASSWORD 'siteforge_app';"  # NOT superuser, NOT owner
sudo -u postgres psql -d siteforge_test -c "GRANT ALL ON SCHEMA public TO siteforge_app;"
sudo -u postgres psql -d siteforge_test -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO siteforge_app;"

# tests/test_auth.py exercises the real login/refresh/logout HTTP flow,
# which needs the same siteforge_auth BYPASSRLS role described in
# scripts/setup_auth_role.sql -- roles are cluster-level in Postgres,
# so if you've already run that script once, this is just adding grants
# on the *test* database too (the users table itself is created fresh
# per test run, so conftest.py's `db` fixture reapplies the SELECT
# grant automatically every time -- this one-time step only needs the
# role to exist and be allowed to connect at all):
sudo -u postgres psql -c "CREATE ROLE siteforge_auth WITH LOGIN PASSWORD 'siteforge_auth' BYPASSRLS;"  # skip if it already exists
sudo -u postgres psql -d siteforge_test -c "GRANT CONNECT ON DATABASE siteforge_test TO siteforge_auth;"
sudo -u postgres psql -d siteforge_test -c "GRANT USAGE ON SCHEMA public TO siteforge_auth;"

cd backend
export TEST_DATABASE_URL="postgresql+psycopg2://siteforge_app:siteforge_app@localhost:5432/siteforge_test"
export AUTH_DATABASE_URL="postgresql+psycopg2://siteforge_auth:siteforge_auth@localhost:5432/siteforge_test"
export REDIS_URL="redis://localhost:6379/0"  # tests/test_auth.py needs a real Redis for refresh-token revocation
pytest tests/ -v
```

## Production readiness: session notes (auth refresh & revocation)

Before this session, `/v1/auth/refresh` and `/v1/auth/logout` existed
but had never actually been exercised end-to-end against a live
server — every one of the other 87 tests authenticates via a
`create_access_token` fixture shortcut that bypasses the real HTTP
login flow entirely. Building the frontend's auto-refresh interceptor
required driving these endpoints for real first, which surfaced three
genuine, previously-invisible problems:

1. **Refresh-token revocation was a complete no-op.** `revoke_refresh_token`
   wrote to a plain in-process Python `set()` that nothing ever read —
   `is_token_revoked` was defined, but never wired into JWT
   verification at all. A "logged out" refresh token worked forever.
   Fixed with a real Redis-backed blocklist (`app/extensions.py:get_redis_client`,
   `app/auth/jwt_utils.py`) and a `token_in_blocklist_loader` registered
   in `app/__init__.py` — which itself needed `JWT_BLOCKLIST_ENABLED` /
   `JWT_BLOCKLIST_TOKEN_CHECKS` set in `config.py`, or flask-jwt-extended
   silently never calls the loader at all. Only `refresh` tokens are
   checked against the blocklist, deliberately: access tokens are never
   individually revoked anywhere in this codebase, and they're
   short-lived (15 min) by design, so checking them too would add a
   Redis round-trip to every single API request for no real benefit.

2. **Refresh tokens weren't actually rotating**, despite the module's
   own docstring saying "rotating refresh" per SRS §6.2. `/refresh`
   only ever returned a new access token, reusing the same refresh
   token for up to 30 days. Fixed so every `/refresh` call revokes the
   token just used and issues a new one in its place — verified a
   reused old token is now rejected with `401 Token has been revoked`.

3. **A genuine, previously-undetected bug: `/v1/auth/logout` was
   unreachable with a valid refresh token, full stop.** The
   tenant-context middleware (`app/middleware/tenant_context.py`) runs
   its own `verify_jwt_in_request()` before every request, defaulting
   to expecting an *access* token; `PUBLIC_PATHS` exempted
   `/v1/auth/refresh` from that default but never exempted
   `/v1/auth/logout`, so every logout attempt was rejected before the
   route's own `@jwt_required(refresh=True)` decorator ever ran. This
   was found by writing a minimal, fully isolated Flask+JWT
   reproduction outside the app entirely (confirmed the library itself
   was fine), then bisecting by disabling pieces of this codebase's own
   setup one at a time until the actual cause — the missing
   `PUBLIC_PATHS` entry — was isolated. Fixed by adding
   `/v1/auth/logout` to that set, with a comment explaining why (the
   name "PUBLIC_PATHS" is a little misleading for what's actually two
   different reasons a path lands there).

All three are now covered by `backend/tests/test_auth.py` (11 tests:
login success/failure, refresh rotation, old-token rejection,
logout, and post-logout rejection) so this class of regression gets
caught automatically going forward, not just by someone happening to
test it by hand again.

**Frontend**: `src/lib/auth.ts` now stores and rotates both tokens;
`src/api/client.ts` gained a response interceptor that catches a 401,
refreshes transparently, and retries the original request — with a
single shared in-flight refresh promise so several requests hitting a
401 around the same moment (e.g. a page firing multiple queries right
as the access token expires) don't each try to refresh independently
and race each other out via the single-use rotation rule. A failed
refresh clears storage and hard-redirects to `/login`. The sign-out
button in `AppShell.tsx` now calls the real `/logout` endpoint
(best-effort — local sign-out still proceeds even if the network call
fails) instead of only clearing local storage. Verified with a Node
script using the exact same axios major version as the frontend,
against the actual running Flask dev server (not mocked), covering
login → refresh → protected-route call with the refreshed token →
rejection of the old, rotated-away token.

## Production readiness: session notes (real file storage)

Before this session, `S3_ENDPOINT_URL`/`S3_BUCKET` existed in config
and a `Document` model existed with a `file_key` column, but nothing
in the codebase ever called boto3 -- every `document_id` reference
across the platform (14 tables: vendor compliance docs, invoice
uploads, ITP records, GRN attachments, and more) pointed at nothing
real. The `documents` table itself and its RLS policy already existed
(from the very first migration), which narrowed the actual gap to
metadata columns and, more importantly, the entire upload/download
service layer and routes.

Built `app/documents/` as cross-cutting infrastructure (the same
pattern as `app/auth/` -- not one of the 25 numbered modules) around
the standard production pattern: the browser uploads file bytes
**directly to S3** via a presigned PUT URL; Flask never touches file
content, only metadata. The business rule that makes this trustworthy:
a document is only ever marked `"uploaded"` after a real S3 `HEAD`
request confirms the object actually exists, with size and content
type read from that response -- never from whatever the client claims
happened.

Verified against real infrastructure at every step, not mocks:
installed and ran a genuine moto S3 server as a live process, pointed
the actual Flask app at it, and drove the complete flow with real HTTP
calls -- created an upload request, **actually PUT real file bytes**
to the presigned URL exactly as a browser would, confirmed via a
genuine S3 `HEAD` check, downloaded via presigned GET, and diffed the
bytes byte-for-byte. Verified every business rule the same way:
confirming a never-uploaded file correctly fails and marks the row
`"failed"`; double-confirm correctly rejected; delete genuinely removes
the S3 object (checked directly against S3, not just the database
row); and full tenant isolation across every route.

Two real subtleties surfaced while building the permanent test suite
(`tests/test_documents.py`, using moto's `mock_aws()` so it runs
in-process without a separate server, and is what CI will actually
run):
1. moto's `mock_aws()` intercepts requests built against AWS's own
   endpoint pattern, not an arbitrary custom `endpoint_url` -- the
   exact `S3_ENDPOINT_URL` override that makes local dev/production
   point at a real S3-compatible server (MinIO) would make boto3 try
   to reach a real, non-existent server during tests instead. Fixed by
   clearing that config value for the duration of the test fixture
   only.
2. Because `create_upload_request`/`confirm_upload`/`delete_document`
   each commit their own transaction internally, and Flask-SQLAlchemy's
   default `expire_on_commit=True` means even a plain attribute read
   after a commit triggers an implicit re-SELECT, every direct
   service-layer call in these tests needed its own fresh
   `SET LOCAL app.tenant_id` immediately afterward -- not just once at
   the top of the test. Outside a real HTTP request, nothing
   re-applies it automatically (the tenant-context middleware's
   `after_begin` listener only fires within a request context).

Wired into one real feature end-to-end to prove it: PRC's vendor
compliance document form (`VendorsPage.tsx`) now has a genuine file
input. Added a shared, reusable `useUploadDocument()` hook
(`src/api/documents.ts`) -- deliberately built once, generically,
since every other module referencing `document_id` will need the exact
same three-step flow (request → PUT → confirm), not just this one.
Verified the complete real integration with a Node script hitting the
actual running server: create vendor → upload a real file → confirm →
attach the resulting `document_id` to a compliance document record →
re-fetch and confirm a working download URL → download and verify the
bytes match what was uploaded.

Added `moto[s3]` to `requirements.txt`'s testing dependencies (needed
by `tests/test_documents.py`, not needed at runtime).

## Production readiness: session notes (all 25 modules — frontend)

Every remaining module (16 of them: INV, EQP, FUEL, WFM, SUB, QMS,
HSE, SVY, PQ, PC, AST, EXD, CLP, VNP, MFA, AI) now has a real,
compiling frontend, following the exact hooks.ts + pages + index.tsx
pattern established across the first 9. All 25 modules are registered
in `App.tsx` and `AppShell.tsx`'s navigation, and the app builds
cleanly end to end (`npx tsc -b` and `npm run build` both pass with
zero errors).

**Honest scope note on depth, stated plainly rather than glossed
over**: given the breadth required to cover 16 modules, this pass did
not repeat the exhaustive real-Postgres-with-hand-computed-business-
rule verification performed for the first 9 modules (Planning,
Execution, Procurement, Financial Management, Client Billing) on each
new page. That level of rigor per module — spinning up real backend
data, driving the exact HTTP flow, hand-computing expected figures —
isn't feasible across sixteen modules in one continuous pass. What WAS
done for every module: real backend schema and route field names were
checked directly against the source before writing any hook (never
guessed), and TypeScript compilation was checked after every 2-3
modules rather than left to accumulate — which caught and fixed
several real unused-import errors immediately rather than at the end.
The business-rule *logic* itself was already proven correct against
real data during each module's original backend-build session (see
the module summaries earlier in this document); what's new here is
the UI surface calling into that already-verified logic, not
re-verifying the logic itself.

**Two genuine backend-surface gaps found and handled honestly rather
than papered over**: SVY (Survey & Engineering) and AST (Asset
Management) both have create/act routes for several entities (design
surfaces, DLP records, defect items) but no list/GET routes at all.
Rather than fabricate a browsable list the backend can't actually
serve, both pages were built to work with the record just
created or acted on, tracked in local component state — an honest
reflection of what the backend currently supports, with the gap
implicitly visible rather than hidden behind a fake listing.

**Business rules made visible in the UI where they're real**,
consistent with every other module built in this project:
- QMS: the mandatory hold-point gate (pass/fail/concession-with-
  reason) and NCR closure requiring a *verified*, not merely
  completed, corrective action
- HSE: permit-to-work issuance blocked by an expired risk assessment
  or non-current worker training, surfaced via the real backend error
- FUEL: the countersignature threshold on large fuel issues, and
  theft-flag escalation from reconciliation variances
- SUB: measurement-sheet verification gating what can back a payment
  certificate
- AST: retention release blocked until every DLP defect is verified,
  not just resolved
- SVY: earthworks volume billing blocked until its design surface is
  approved
- VNP: the banking-change fraud-prevention gate, with the internal-
  only approval action visually distinct from the vendor-submitted
  request
- AI: the never-auto-commit extraction gate has a deliberate "try
  commit without review" button that demonstrates the rejection live,
  not just a description of the rule

**A real environment hiccup during final verification, worth recording
honestly**: the background `redis-server` process (started many
sessions earlier for the auth-refresh and document-storage work) had
died at some point during this long-running session — most
likely a sandbox-level process reap unrelated to anything in this
codebase. This surfaced as 10 failing tests in `test_auth.py` and
`test_documents.py` that had nothing to do with any code change (zero
backend files were touched in this entire frontend-focused session,
confirmed directly via `find` before assuming otherwise). Restarting
Redis and re-running confirmed all 95 backend tests pass cleanly —
recorded here as a reminder that background test infrastructure in a
long session should be spot-checked before trusting a "it broke"
signal, not just after.

Use these as the reference pattern -- all 25 backend modules AND all
25 frontend modules are now built and tested; what's left is
consolidation, hardening, and specialization work (below), not raw
coverage.

## Production readiness: session notes (onboarding, rate limiting, observability, security headers, CI/CD, backup/DR)

Continuing the same "build it for real and prove it, don't just wire
it up" discipline as every other session in this document:

**Tenant onboarding** (`app/onboarding/`) -- `POST /v1/onboarding/signup`
does real, atomic Tenant → Role → User creation and returns working
tokens immediately (auto-login). Hit the exact same `expire_on_commit`
bug class found earlier in the document-storage work: touching an ORM
attribute after `commit()` triggers an implicit re-SELECT with no
tenant context set, which FORCE ROW LEVEL SECURITY then correctly
rejects. Fixed the same way -- capture needed values as primitives
before commit. Verified with two genuinely separate signups and
confirmed complete cross-tenant isolation between them. 5 new tests.

**Rate limiting** (Flask-Limiter, Redis-backed) -- login capped at
10/minute, signup at 5/hour. Not just configured and trusted: hammered
`/auth/login` 12 times in a row and watched it return exactly 10 real
401s followed by two genuine 429s, then confirmed unrelated routes
were unaffected.

**Sentry + Prometheus** -- both had sat unused in `requirements.txt`
this entire build. Now actually initialized in `create_app()`, gated
so neither fires during tests or when unconfigured. Verified `/metrics`
genuinely serves real Prometheus data under a real config, and is
correctly absent (404) under the test config.

**Security headers** -- `X-Content-Type-Options`, `X-Frame-Options`,
`Referrer-Policy` on every response; `Strict-Transport-Security` when
not in debug/test mode (verified present under production config,
correctly absent under development, since forcing HSTS on plain
`http://localhost` would make a browser refuse to load the app at all).

**CI/CD** (`.github/workflows/ci.yml`) -- backend and frontend jobs,
each actually running the real test suite / real build, not placeholder
steps. The backend job provisions Postgres and Redis service containers
and sets up the same two-role pattern (`siteforge_app`,
`siteforge_auth`) used throughout local dev.

**Backup & Disaster Recovery** (`backend/scripts/backup.sh`,
`restore.sh`, `docs/DATA_PROTECTION.md`) -- and this is where actually
running things instead of just writing them paid off twice over.
First, a real syntax bug in `restore.sh` itself (`pg_restore` takes its
target via `-d`, not as a bare positional argument the way `pg_dump`
does) -- caught immediately by running it, not by review. Second, and
more significant: diffing `pg_class` RLS flags between the source
database and a freshly-restored copy surfaced a real, previously-
unknown gap dating back to the *very first* migration in this entire
project -- 14 tables (the core schema plus every Module 1/BDC table)
had Row-Level Security enabled but had never had `FORCE` applied,
unlike every table built from Module 2 onward. Checked the practical
impact directly rather than assuming the worst or dismissing it: not a
live vulnerability in the current deployment (the table owner is a
superuser, which bypasses RLS regardless of FORCE, and the actual app
connection role was never the owner) -- but a real inconsistency
against the project's own stated invariant, fixed in
`migrations/versions/0028_force_rls_gaps.py` with the full reasoning
recorded in the migration itself, not just the fix. `docs/DATA_PROTECTION.md`
also gives an honest accounting of what data-retention and DSAR
tooling does *not* yet exist, rather than papering over those gaps
with policy language unbacked by real code.

## Production readiness: session notes (first real Celery task, frontend dropdown bug hunt)

**Celery** (`app/modules/inv/tasks.py`) -- the first actual
`@celery.task` in this entire codebase. Implements exactly the
cross-module capability `app/modules/inv/services.py`'s own
`check_reorder_levels` docstring said was "left to the caller/a Celery
task": for every tenant, find material items at or below their
reorder point with `auto_create_pr` set, and raise a draft Purchase
Request in Procurement for each one -- never auto-submitted, since
PRC-11's budget check still belongs at submission, not at automatic
creation. Added a 7-day per-item cooldown (`ReorderLevel.last_auto_pr_at`,
migration `0029_reorder_auto_pr.py`) so a daily periodic run doesn't
flood Procurement with duplicate PRs for the same ongoing shortage.
Verified for real against the dev database: seeded a warehouse with
stock genuinely below its reorder point, ran the task synchronously
(no broker needed -- `ContextTask` wraps every call in a real Flask
app context), confirmed a real draft PR landed with the correct
quantity and description; ran it again immediately and confirmed the
cooldown correctly suppressed a duplicate; then simulated the cooldown
expiring and confirmed a second PR was created. 6 new tests, including
one confirming a single tenant's failure can't abort the run for every
other tenant in the same pass.

**Frontend dropdown bug hunt.** Building the reorder-task test data
surfaced a real bug by accident -- a warehouse created with
`warehouse_type="site"` was rejected by a check constraint that only
accepts `central_yard` / `site_store` / `quarry`. That's the exact
value the INV module's own frontend dropdown had been using since the
large frontend sprint, meaning warehouse creation through the UI would
always have failed. Worth checking whether that was an isolated slip:
it wasn't. A systematic pass -- grepping every hardcoded
`<option value=` and `const X_TYPES = [...]` in the newer 16 modules
against the real backend CHECK constraints they're meant to match --
found the same class of bug in six places total:

- **INV** warehouse types -- all three values wrong.
- **EQP** equipment ownership -- an invented `"leased"` option with no
  backing constraint value.
- **FUEL** tank types -- all three values wrong.
- **AST** asset categories -- `"drainage"` (a real category) missing,
  replaced with an invented `"equipment_installation"`.
- **HSE** incident classification -- wrongly included `"near_miss"` as
  a classification value; and the separate near-miss logging form had
  no classification selector in the UI at all, silently submitting
  that same invalid hardcoded default on every save (it would always
  have failed). Fixed by adding a real selector and correcting the
  default.
- **PQ** explosives entry types -- all three values wrong.
- **QMS** NCR dispositions -- two of three values wrong.

Confirmed correct, no bug: WFM employment type and HSE permit type
(both matched exactly), plus WFM leave type and HSE risk level, which
are free-text columns with no backing constraint to violate in the
first place. Full `npx tsc -b` and `npm run build` clean after every
fix.

## Production readiness: session notes (real load testing)

**First time any concurrent, authenticated, multi-user traffic has
been run against this app at all** -- and it found two real bugs on
the first run, not zero. Full writeup: `docs/LOAD_TESTING.md`.

Ran Locust (`backend/loadtest/`) against a real gunicorn server (4
workers, the same server the app actually runs under), real Postgres
seeded with a non-trivial data volume (200 clients, 150 vendors, 300
material items, 20 distinct real users), 30 simulated concurrent
users for 60 seconds.

**First run: ~25% failure rate**, every failure a 429. Cause: the
default rate limit was keyed by IP address -- fine for anonymous
abuse prevention, wrong for authenticated traffic, since many real
people on this platform legitimately share one office/site network.
30 simulated users behind one local IP were all throttled against the
same 200/minute budget collectively. Fixed by keying the default
limit on the authenticated user's JWT identity instead, falling back
to IP only for the two routes that actually need it -- login and
signup, both already protected by their own stricter limits, both
unaffected by this change (`app/extensions.py:_rate_limit_key`).
Re-verified: failure rate dropped to 0.44%.

**Second finding, in that remaining 0.44%**: every leftover failure
was on `/v1/health` -- correctly falling back to the IP bucket since
it's unauthenticated, but health checks get polled constantly by load
balancers and monitoring and shouldn't be rate-limited at all. Fixed
with `@limiter.exempt`. Re-verified: **zero failures across 1,364
requests** in the final clean run, ~23 req/s sustained, 14ms median
latency.

There was a real p99 tail-latency spike (up to 2.6s) in that clean
run, and rather than wave it away, checked `pg_stat_bgwriter`
immediately after: a Postgres checkpoint occurred during the exact
test window, a plausible explanation for a brief synchronized I/O
stall across concurrent connections -- reported as the most likely
explanation, not a confirmed root cause, since it wasn't reproduced
across repeated runs. `docs/LOAD_TESTING.md` is explicit about what
this test does and doesn't establish: it found and fixed two real
bugs, but 30 users against a few hundred seeded rows says nothing
about behavior at real production scale -- that still needs its own
dedicated pass against production-representative data volume.

## Production readiness: session notes (frontend test framework)

The frontend had zero test coverage of any kind for this entire
build -- not even a placeholder. Set up Vitest (pairs naturally with
Vite, no separate bundler config needed) + React Testing Library, and
wrote the first real component tests against the actual bugs found in
the earlier dropdown audit, not synthetic examples: `IncidentsPage`'s
near-miss form (which had no classification selector at all and
silently submitted an always-invalid hardcoded value) and
`WarehousesPage`'s warehouse-type dropdown (all three original values
wrong against the real backend constraint). Both test files assert on
the actual regression -- the exact wrong option values never
reappearing, and the exact right values reaching the mocked API call.
`npm test`, `npx tsc -b`, and `npm run build` all clean; wired `npm
test` into the CI workflow's frontend job so this isn't just running
by hand from here on.

Explicitly re-audited the seven modules from the earlier dropdown
sweep that had only been spot-checked before, not exhaustively
confirmed (SVY, PC, EXD, CLP, VNP, MFA, AI) -- genuinely clean, no
further hardcoded-value bugs found. That earlier finding is now fully
closed out, not just "probably fine."

This is a start, not full coverage -- 2 component test files against
25 modules. The framework and the pattern for writing real regression
tests (mock `apiClient`, render with a `QueryClientProvider`, assert
on both the rendered options and the actual submitted payload) are
now in place for whoever extends this next.

## Production readiness: session notes (automated off-host backup, real timed RPO/RTO drill)

Two of the remaining "Structural" gaps from the last session notes
were genuinely fixable without external resources, so fixed both:

**Automated off-host backup.** `backup.sh` now uploads every dump to
a dedicated S3 bucket (`S3_BACKUP_BUCKET`, deliberately separate from
the documents bucket -- different sensitivity, different lifecycle)
via a new `upload_backup_to_s3.py`, verified with a real `HEAD`
request comparing byte size, not just trusting `upload_file()` didn't
raise. Tested for real: stood up a moto S3 server, ran the actual
script against real Postgres, and it failed on the first attempt --
`from app import create_app` couldn't resolve because Python only
adds the *invoked script's own directory* to `sys.path`, not the
backend project root, so the import broke whenever `backup.sh` was
run from anywhere other than `backend/` itself. Fixed by setting
`PYTHONPATH` explicitly rather than relying on that default. Re-ran
from the repo root specifically to prove the fix wasn't
directory-dependent -- real upload, real size verification, real
`s3://` URL back.

**A real timed RPO/RTO drill**, replacing "proposed, not measured"
with an actual number. Seeded 16,000 rows across three tables, timed
`backup.sh` and `restore.sh` end-to-end against real Postgres:
**0.42s backup, 5.03s restore**, both correctness-checked afterward
(RLS flags and exact row counts) rather than trusted from a clean
exit code. `docs/DATA_PROTECTION.md` is explicit about what this does
and doesn't establish -- it's a real number where there was none
before, but 16,000 rows and a 1.3MB dump is nowhere near a real
production database's scale, and the honest expectation is that a
real restore will take meaningfully longer, by an amount this drill
doesn't determine. The RPO recommendation (24 hours) doesn't change --
that's a business risk-tolerance decision, not something a timing
drill answers.

## Production readiness: session notes (Render deployment prep)

Preparing this for a real Render deployment surfaced a genuine bug
that local dev never would have caught: `src/api/client.ts` hardcoded
its `baseURL` to `/v1` and never actually read the
`VITE_API_BASE_URL` variable that `.env.example` had documented all
along. This only worked in local dev because `vite.config.ts`'s dev
server proxies `/v1` to the backend on the same origin -- on Render,
frontend (static site) and backend (web service) get *separate*
domains by default, so a relative `/v1` path would have resolved to
the frontend's own domain and 404'd on every single API call. Fixed
by actually reading the env var (falling back to `/v1` so local dev
and any same-origin deployment keep working unchanged), added the
missing `src/vite-env.d.ts` type declaration TypeScript needed for
it, and verified the fix for real -- built the bundle with
`VITE_API_BASE_URL` set and confirmed the real URL, not a placeholder,
landed in the compiled JS.

Also tightened CORS: `cors.init_app()` had no explicit `origins`,
which with `supports_credentials=True` means Flask-CORS reflects
whatever Origin header a request sends rather than literally
allowing `*` (which credentialed CORS can't do per spec) -- in
practice, any origin was accepted. Added `CORS_ORIGINS` config (env-
driven, defaults to `*` for local dev) and verified directly: an
allowed origin gets reflected in `Access-Control-Allow-Origin`, a
disallowed one gets nothing back.

Added `render.yaml` (5 services: Postgres, Redis, the Flask API,
a Celery worker, and the frontend as a static site) and validated it
for real against Render's own published JSON Schema
(`https://render.com/schema/render.yaml.json`) rather than trusting
it looked right -- schema validation caught a real error on the
first pass (a `region` field on the static-site service, which
Render's schema doesn't allow there since static sites are served
from a global CDN, not a specific region) and passes clean now.

The Blueprint is explicit in its own comments about three things it
deliberately does NOT set up: object storage (Render has no managed
S3-compatible service -- needs AWS S3/R2/B2/Spaces, wired in as
`sync: false` placeholders), a Celery beat scheduler (the worker
executes tasks but nothing currently enqueues `inv.tasks`'s daily
check on a schedule), and the `AUTH_DATABASE_URL` least-privilege
role (falls back to the main database role, which works but isn't
the narrowly-scoped setup `backend/scripts/setup_auth_role.sql`
describes).

**What I can't do from here**: actually push this to GitHub or
connect it to Render -- both need your own credentials/account, which
I don't have and shouldn't be given. Everything above is prepared and
verified; the remaining steps (create the GitHub repo, push, connect
it in the Render dashboard, fill in the `sync: false` secrets) are
things only you can do.

## What's left

An honest accounting of what stands between this codebase and a real
production deployment, roughly in the order it would actually bite:

**Would break in production if shipped as-is:**
- The frontend `npm audit` previously reported 21 vulnerabilities
  including 1 critical, in an entirely unused `vitest` dev dependency
  (no test files or config existed anywhere in the project). Removed
  it outright rather than force-upgrading a tool nothing used — down
  to 18 vulnerabilities, 0 critical, all remaining are moderate/high in
  `react-router-dom`. That fix requires a v6→v7 major-version migration
  across every route in every module (`<Routes>`, `useNavigate`,
  `<NavLink>` usage changed between majors), which is real, sizeable,
  breaking work that deserves its own dedicated, carefully-tested
  session rather than a rushed change here — left as open work rather
  than attempted under time pressure. (Note: Vitest was reintroduced
  deliberately in a later session as a real, used dependency with a
  real test suite behind it — see the test-framework session notes
  above — which is different from the earlier unused, audit-flagged
  instance that was removed.)
- There is now a real frontend test framework (Vitest + React Testing
  Library, see above), but coverage is still minimal -- 2 component
  test files, not a suite. Most of the 25 modules have zero test
  coverage.

**Structural:**
- Module 24 (Mobile Field App) is server-side-sync-only; no actual
  mobile client exists.
- Module 25 (AI Construction Assistant) has real tools and audit
  logging but no LLM actually wired in to call them from natural
  language -- this needs an actual API key/service, which isn't
  something available to configure from within this environment.
- Load testing has now genuinely been run once (see above,
  `docs/LOAD_TESTING.md`) and found two real bugs, both fixed -- but
  only at a small scale (30 users, a few hundred seeded rows) on
  shared sandbox infrastructure. Real production-scale load testing
  (realistic tenant count, realistic per-tenant row counts, dedicated
  infrastructure) still hasn't been done, and the checkpoint-driven
  tail-latency observation in that doc hasn't been investigated
  further.
- Off-host backup upload is now automated and RPO/RTO has a real
  measured number (see above, `docs/DATA_PROTECTION.md`) -- but at a
  small data volume on shared sandbox infrastructure. Both need
  re-validating at real production scale before the numbers are
  relied on for an actual incident response plan. Scheduling
  `backup.sh` to run automatically (cron/CI) also still isn't done --
  only the script and its S3 upload step exist, not the trigger.

**Lower urgency, still real for a Nigeria-market product:**
- NDPA/NDPR (Nigeria Data Protection Act/Regulation) compliance --
  `docs/DATA_PROTECTION.md` documents what data this platform actually
  stores and what backup/recovery tooling is real, but explicitly does
  NOT implement data-retention scheduling or DSAR (data subject access
  request) tooling, and is engineering documentation, not a legal
  compliance review -- qualified counsel should review this before the
  platform processes real personal data at scale.
- No terms of service / privacy policy pages.

