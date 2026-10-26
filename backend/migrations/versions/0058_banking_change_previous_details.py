"""keep prior banking details when a change is approved

Revision ID: 0058_bank_prev_details
Revises: 0057_clp_pwd_changed_at
Create Date: 2026-10-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0058_bank_prev_details"
down_revision = "0057_clp_pwd_changed_at"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("vnp_banking_change_requests", sa.Column("previous_banking_details", postgresql.JSONB, nullable=True))


def downgrade():
    op.drop_column("vnp_banking_change_requests", "previous_banking_details")
