"""force rls on core and bdc tables
force rls on core and bdc tables
Revision ID: 0028_force_rls_gaps
Revises: 0027_documents
Create Date: 2026-07-31

Found by actually testing a backup/restore round-trip
(backend/scripts/backup.sh and restore.sh) against real Postgres and
diffing pg_class flags between the source and restored databases:
`documents` had ROW LEVEL SECURITY enabled since the very first
migration (0001_core.py), but never had FORCE applied. Checking
whether that was an isolated miss or a pattern turned up 14 tables
with the same gap, not just one -- every table created in 0001_core.py
(tenants excluded, correctly -- it's the un-scoped root of the tenant
hierarchy) plus every table in Module 1 (BDC), which together make up
the earliest schema built in this project, before the
ENABLE + FORCE pairing became the consistently-applied pattern used by
every one of modules 2 through 25. TenantMixin's own docstring
documents ENABLE + FORCE as the required pair for every tenant-scoped
table -- this closes a real, systemic gap against that stated
invariant across the oldest part of the schema.

Practical impact assessment: NOT a live vulnerability in the current
deployment topology. FORCE only affects the table's OWNING role's own
RLS exemption, and every affected table (like all tables in this
schema) is owned by the `siteforge` superuser, which bypasses RLS
regardless of FORCE -- superuser status itself is the actual
exemption, and FORCE cannot override it. The actual application
connection role (`siteforge_app`) is not the table owner and was
already correctly subject to RLS on every one of these tables with or
without FORCE -- the 76-test tenant-isolation suite passing throughout
this entire build already proves that empirically. This migration is
a defense-in-depth correction for consistency with the rest of the
schema, and closes what WOULD become a live gap if table ownership
were ever changed away from a superuser (a common production
hardening step) without this fix already in place.

Scope note: this migration only matters for databases actually
provisioned via `flask db upgrade` (real dev/staging/production
environments). The test suite's own schema setup
(tests/conftest.py:_enable_rls_for_all_tenant_scoped_tables) builds
its schema from SQLAlchemy metadata directly via db.create_all() and
already applies ENABLE + FORCE correctly for every tenant-scoped
table, every test run, completely independent of the migration files
-- which is exactly why the isolation suite never caught this gap in
the first place: its own schema was never exposed to it. Only the
migration-based path had the inconsistency.
"""
from alembic import op

revision = "0028_force_rls_gaps"
down_revision = "0027_documents"
branch_labels = None
depends_on = None

AFFECTED_TABLES = [
    "documents",
    "projects",
    "users",
    "companies",
    "roles",
    "bdc_clients",
    "bdc_leads",
    "bdc_proposals",
    "bdc_opportunities",
    "bdc_consultants",
    "bdc_win_loss_records",
    "bdc_contacts",
    "bdc_government_agencies",
    "bdc_competitors",
]


def upgrade():
    for table in AFFECTED_TABLES:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade():
    for table in AFFECTED_TABLES:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
