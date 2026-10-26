"""documents: portal owner

Revision ID: 0059_doc_portal_owner
Revises: 0058_bank_prev_details
Create Date: 2026-10-26

Links a document to the subcontractor / vendor organisation whose portal
user uploaded it, so portal users can list their own organisation's
documents and staff can tell where an upload came from.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0059_doc_portal_owner"
down_revision = "0058_bank_prev_details"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("documents", sa.Column("portal_owner_type", sa.String(8), nullable=True))
    op.add_column("documents", sa.Column("portal_owner_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_documents_portal_owner_id", "documents", ["portal_owner_id"])
    op.create_check_constraint(
        "ck_documents_portal_owner_type", "documents", "portal_owner_type IS NULL OR portal_owner_type IN ('scp','vnp')"
    )


def downgrade():
    op.drop_constraint("ck_documents_portal_owner_type", "documents", type_="check")
    op.drop_index("ix_documents_portal_owner_id", table_name="documents")
    op.drop_column("documents", "portal_owner_id")
    op.drop_column("documents", "portal_owner_type")
