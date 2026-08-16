"""est budget revision status

Revision ID: 0037_est_revision_status
Revises: 0036_eqp_cutover_tracking
Create Date: 2026-08-15

Adds a real status concept to est_budget_revisions -- previously
absent entirely. A revision self-approved immediately on creation
(approved_by was always the same actor who created it, no real
second-approval gate), despite BudgetRevision being explicitly
documented as "the only sanctioned way to change an approved CBS
baseline." Defaults every existing row to 'approved' -- preserves
exact current behavior for every tenant that hasn't (and, until this
migration, couldn't have) configured a Workflow Engine chain for this
entity type. Revision ID kept short deliberately, learned from
0036's own history: alembic_version.version_num is varchar(32).
"""
from alembic import op
import sqlalchemy as sa

revision = "0037_est_revision_status"
down_revision = "0036_eqp_cutover_tracking"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "est_budget_revisions",
        sa.Column("status", sa.String(16), nullable=False, server_default="approved"),
    )
    op.execute(
        "ALTER TABLE est_budget_revisions ADD CONSTRAINT ck_est_revision_status "
        "CHECK (status IN ('approved', 'pending', 'rejected'))"
    )


def downgrade():
    op.execute("ALTER TABLE est_budget_revisions DROP CONSTRAINT ck_est_revision_status")
    op.drop_column("est_budget_revisions", "status")
