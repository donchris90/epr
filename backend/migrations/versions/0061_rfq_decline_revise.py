"""RFQ: vendor decline reason and quote revision tracking

Revision ID: 0061_rfq_decline_revise
Revises: 0060_claim_support_doc
Create Date: 2026-10-26

A vendor can decline an RFQ invitation (optional reason) and revise their
quote until the RFQ closes. Both are recorded so procurement can see them.
"""
from alembic import op
import sqlalchemy as sa

revision = "0061_rfq_decline_revise"
down_revision = "0060_claim_support_doc"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("prc_rfq_invitations", sa.Column("decline_reason", sa.Text(), nullable=True))
    op.add_column("prc_rfq_invitations", sa.Column("declined_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("prc_rfq_quotations", sa.Column("revised_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "prc_rfq_quotations",
        sa.Column("revision_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_column("prc_rfq_quotations", "revision_count")
    op.drop_column("prc_rfq_quotations", "revised_at")
    op.drop_column("prc_rfq_invitations", "declined_at")
    op.drop_column("prc_rfq_invitations", "decline_reason")
