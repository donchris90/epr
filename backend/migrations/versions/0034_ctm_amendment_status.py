"""ctm contract amendment status

Revision ID: 0034_ctm_amendment_status
Revises: 0033_notifications
Create Date: 2026-08-15

Adds a real status concept to ctm_contract_amendments -- previously
absent entirely. Amendments self-approved immediately on creation
(approved_by was always the same actor who created it, no real
second-approval gate), despite having approved_by/approved_at fields
that suggest an approval control existed. Defaults every existing row
to 'approved' -- preserves exact current behavior for every tenant
that hasn't (and, until this migration, couldn't have) configured a
Workflow Engine chain for this entity type.

Local testing note: ALTER TABLE ADD COLUMN requires being the table's
OWNER, not just DDL privileges on the schema -- this only surfaced
because this sandbox's tables were created via a superuser connection
during local setup, not the same role now applying this migration
(siteforge_app). In production, the single Render-provisioned role
both creates every table from migration 0001 onward AND runs every
subsequent migration, so it already owns everything it created --
this specific class of failure can't occur there. Confirmed by
matching local ownership to that reality and re-running: the
migration applies cleanly.
"""
from alembic import op
import sqlalchemy as sa

revision = "0034_ctm_amendment_status"
down_revision = "0033_notifications"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "ctm_contract_amendments",
        sa.Column("status", sa.String(16), nullable=False, server_default="approved"),
    )
    op.execute(
        "ALTER TABLE ctm_contract_amendments ADD CONSTRAINT ck_ctm_amendments_status "
        "CHECK (status IN ('approved', 'pending', 'rejected'))"
    )


def downgrade():
    op.execute("ALTER TABLE ctm_contract_amendments DROP CONSTRAINT ck_ctm_amendments_status")
    op.drop_column("ctm_contract_amendments", "status")
