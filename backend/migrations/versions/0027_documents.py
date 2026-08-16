"""documents metadata columns

Revision ID: 0027_documents
Revises: 0026_ai
Create Date: 2026-07-31

Adds the metadata columns app/documents/services.py needs to actually
run a real upload/confirm/download lifecycle: original_filename,
content_type, size_bytes, status, uploaded_by. The `documents` table
itself and its RLS policy already existed (created in 0001_core.py) --
this migration only adds columns, no new table and no RLS changes.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0027_documents"
down_revision = "0026_ai"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("documents", sa.Column("original_filename", sa.String(255), nullable=True))
    op.add_column("documents", sa.Column("content_type", sa.String(128), nullable=True))
    op.add_column("documents", sa.Column("size_bytes", sa.BigInteger, nullable=True))
    op.add_column("documents", sa.Column("status", sa.String(16), nullable=False, server_default="pending"))
    op.add_column("documents", sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_check_constraint("ck_documents_status", "documents", "status IN ('pending','uploaded','failed')")


def downgrade():
    op.drop_constraint("ck_documents_status", "documents", type_="check")
    op.drop_column("documents", "uploaded_by")
    op.drop_column("documents", "status")
    op.drop_column("documents", "size_bytes")
    op.drop_column("documents", "content_type")
    op.drop_column("documents", "original_filename")
