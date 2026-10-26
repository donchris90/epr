"""subcontract claims: supporting document

Revision ID: 0060_claim_support_doc
Revises: 0059_doc_portal_owner
Create Date: 2026-10-26

Optional evidence file for a subcontractor claim, one of the uploaded
documents the subcontractor's own organisation holds in the portal.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0060_claim_support_doc"
down_revision = "0059_doc_portal_owner"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "sub_claims",
        sa.Column("supporting_document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
    )


def downgrade():
    op.drop_column("sub_claims", "supporting_document_id")
