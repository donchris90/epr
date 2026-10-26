"""DSAR: public intake source, email verification, requester notification

Revision ID: 0062_dsar_public_intake
Revises: 0061_rfq_decline_revise
Create Date: 2026-10-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0062_dsar_public_intake"
down_revision = "0061_rfq_decline_revise"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("dsar_requests", sa.Column("source", sa.String(8), nullable=False, server_default="staff"))
    op.add_column("dsar_requests", sa.Column("verification_token_hash", sa.String(64), nullable=True))
    op.add_column("dsar_requests", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("dsar_requests", sa.Column("requester_notified_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint("ck_dsar_requests_source", "dsar_requests", "source IN ('staff', 'public')")


def downgrade():
    op.drop_constraint("ck_dsar_requests_source", "dsar_requests", type_="check")
    op.drop_column("dsar_requests", "requester_notified_at")
    op.drop_column("dsar_requests", "email_verified_at")
    op.drop_column("dsar_requests", "verification_token_hash")
    op.drop_column("dsar_requests", "source")
