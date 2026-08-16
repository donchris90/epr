# Data Protection & Backup/Recovery

This document is engineering documentation, not legal advice. It
describes what the system actually does and provides operational
procedures; it is not a substitute for review by qualified legal
counsel before this platform processes real personal data at scale,
particularly regarding obligations under the Nigeria Data Protection
Act 2023 (NDPA) and its predecessor regulation (NDPR).

## What personal data this platform actually stores

Per-tenant, isolated by Row-Level Security (see README.md's
architecture section for how RLS is enforced):

- **Users** (`users` table): email, password hash (Argon2, never
  plaintext), role assignment.
- **Employees & casual workers** (Module 11, Workforce Management):
  name, phone, trade, employment type, pay rate, certifications.
- **Client & vendor contacts** (Modules 1, 7, 22, 23): names, emails,
  organization affiliations.
- **Uploaded documents** (`documents` table + S3-compatible object
  storage, see `app/documents/`): whatever files a tenant's users
  upload -- compliance documents, invoices, inspection photos, and
  similar. Content is opaque to this document -- what's in an
  uploaded file is under the tenant's control, not the platform's.

## Data retention

No automated retention/deletion policy is implemented in this
codebase as of this writing. Data persists indefinitely once created,
across every module, until manually deleted through whatever delete
routes exist for that entity (most entities in this platform are
designed to be immutable audit records -- e.g. journal entries,
progress certificates -- and deliberately have no delete route at
all, by design, for audit-trail integrity).

**Before processing real personal data**, a genuine retention policy
needs to be decided (how long after an employee leaves, a contract
ends, or a tenant closes their account should personal data be
retained) and then implemented as actual scheduled deletion logic --
this does not exist yet and is explicitly called out as an open gap
in README.md's "What's left" section.

## Data Subject Access Requests (DSAR)

No dedicated DSAR tooling exists. Today, fulfilling a request from an
individual to see, correct, or delete their personal data would
require a manual database query by tenant administrators or platform
operators, scoped by the RLS tenant boundary already in place.

A real DSAR process, before this matters in production, needs:
1. An intake channel (a documented email address or in-app form) --
   not built.
2. A way to search across all modules a given email/name appears in
   within one tenant -- not built; would need a cross-module search
   utility, since personal data isn't centralized (it lives in
   whichever module created it: BDC contacts, WFM employees, CLP
   client users, etc.).
3. A documented response-time commitment.

## Backup & Disaster Recovery

**This part is implemented and tested**, unlike retention/DSAR above.

- `backend/scripts/backup.sh` -- takes a compressed `pg_dump` (custom
  format, `-Fc`), verifies the dump is actually readable immediately
  after writing it (not just that the command exited 0), and prunes
  backups older than 30 days from the target directory.
- `backend/scripts/restore.sh` -- restores a dump produced by
  `backup.sh` into a target database, and prints the verification
  queries below for confirming the restore is trustworthy before
  treating it as live.

Both scripts were run for real against this project's own database
during development (not just written and assumed to work) -- and
that real test caught two genuine issues, not zero:
1. A syntax bug in `restore.sh` itself (`pg_restore` takes its
   connection target via `-d`, not as a bare positional argument the
   way `pg_dump` does) -- found and fixed by actually running it.
2. A real, previously-unknown gap in the schema itself: 14 tables
   (the earliest ones built in this project -- the core schema and
   Module 1/BDC) had Row-Level Security enabled but never had `FORCE`
   applied, unlike every table built afterward. Diffing `pg_class`
   flags between the source and a freshly-restored copy is what
   surfaced this. See `migrations/versions/0028_force_rls_gaps.py`
   for the fix and a full practical-impact assessment (short version:
   not a live vulnerability in the current deployment, because the
   table owner is a superuser which bypasses RLS regardless of
   FORCE -- but a real inconsistency worth closing, especially before
   any future move away from superuser-owned tables).

### Recommended backup schedule (upload automated, scheduling not yet automated)

A cron job or scheduled CI job should run `backup.sh` daily -- that
scheduling wrapper doesn't exist yet, only the script itself. What
*is* now automated: every run of `backup.sh` uploads the dump to a
dedicated S3 bucket (`S3_BACKUP_BUCKET`, separate from the documents
bucket for isolation) and verifies the upload with a real `HEAD`
request comparing byte size, the same "never trust a write succeeded
just because the call didn't raise" discipline used for document
uploads (see `backend/scripts/upload_backup_to_s3.py`). Verified for
real: ran the full script against real Postgres with a real (moto)
S3 server standing in for the object store, confirmed the dump landed
and the size check passed -- and that test caught a real path bug on
the first attempt (the upload step failed to import the `app` package
when invoked from outside the `backend/` directory; fixed by setting
`PYTHONPATH` explicitly rather than relying on Python's default
script-relative path). `SKIP_S3_UPLOAD=1` bypasses the upload for a
local-only dev backup. Local-disk-only backups still don't survive
the loss of the host they were taken on -- that's exactly what this
closes.

### Recovery Point / Recovery Time: real measured numbers, at a small scale

An actual timed drill was run: seeded 16,000 rows across three tables
(5,000 clients, 3,000 vendors, 8,000 material items) under one tenant,
then timed `backup.sh` and `restore.sh` against real Postgres,
end-to-end, wall-clock.

- **Backup: 0.42 seconds** for a 1.3MB dump.
- **Restore: 5.03 seconds**, including the dump being read back and
  every table recreated.
- Correctness re-verified afterward, not assumed from a clean exit
  code: `documents` showed `relrowsecurity=t, relforcerowsecurity=t`
  (confirming the RLS fix in `0028_force_rls_gaps.py` survives a
  restore), and both seeded row counts (5,000 clients, 8,000 material
  items) matched exactly.

**What this does and doesn't establish**, the same distinction drawn
in `docs/LOAD_TESTING.md` for the load test: this replaces "never
measured" with a real number, which is worth something -- but 16,000
rows and a 1.3MB dump is nowhere near a real production database after
months or years of multi-tenant transactional history (which could
run into the many gigabytes). Both `pg_dump`/`pg_restore` time scale
with data volume, and neither scales linearly in a simple way once
indexes, foreign keys, and WAL replay are involved at real scale. The
timing here also reflects this sandboxed environment's shared
infrastructure, not dedicated production hardware.

Based on this real result plus the above caveats:

- **RPO: 24 hours** remains the recommendation, matching a daily
  backup schedule. This part isn't a timing question -- it's a
  question of how much data loss is acceptable, and 24 hours is a
  starting point pending an actual business decision, not something
  this drill changes. Achieving a tighter RPO (minutes) needs
  continuous WAL archiving / point-in-time recovery, a real
  infrastructure addition beyond the daily-dump approach here.
- **RTO: measured at 5 seconds at this scale.** The honest
  extrapolation is that a real production restore -- provisioning a
  fresh Postgres instance, transferring a much larger dump, and
  replaying it -- will take meaningfully longer than 5 seconds, likely
  by orders of magnitude, and the *shape* of that scaling hasn't been
  tested here. Before this number is relied on for a real incident
  response plan, the same drill needs to be re-run against a database
  seeded to realistic production row counts, on infrastructure that
  matches (or exceeds) the real deployment target.

### Restore drill discipline

`restore.sh` deliberately restores into whatever database
`DATABASE_URL` points at -- always point it at a **fresh, empty**
database for a drill, never the live one, so a mistake mid-drill can't
corrupt production data. Promote a restored database to "live" only
after running the three verification queries the script itself prints
at the end.
