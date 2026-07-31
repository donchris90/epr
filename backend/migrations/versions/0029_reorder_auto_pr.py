"""reorder level auto-PR cooldown tracking

Revision ID: 0029_reorder_auto_pr
Revises: 0028_force_rls_gaps
Create Date: 2026-07-31

Adds the field app/modules/inv/tasks.py needs to avoid creating a new
draft Purchase Request every single time the periodic reorder check
runs while a material item stays below its reorder point (which could
otherwise be hourly/daily for as long as the shortage lasts, flooding
Procurement with duplicate PRs for the same underlying need).
"""
from alembic import op
import sqlalchemy as sa

revision = "0029_reorder_auto_pr"
down_revision = "0028_force_rls_gaps"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("inv_reorder_levels", sa.Column("last_auto_pr_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("inv_reorder_levels", "last_auto_pr_at")
