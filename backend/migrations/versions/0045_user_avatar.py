"""user avatar

Revision ID: 0045_user_avatar
Revises: 0044_cleanup_orphan_email_idx
Create Date: 2026-08-19

Real avatar support, reusing the existing document/S3 infrastructure
(app/documents/) rather than building a separate image storage system
-- an avatar is just a Document row like any other, with a real
content-type check applied specifically when it's set as someone's
avatar (see app/auth/services.py).

Added as NOT VALID, not an inline ForeignKey, matching the same real
issue found and fixed for Project's own client_id/project_manager_id
columns (migration 0042): an inline FK triggers Postgres to validate
existing rows against the referenced table immediately, and documents
has FORCE RLS like every other tenant-scoped table in this platform --
that validation query would fail with no app.tenant_id set during a
schema migration. Safe regardless: this is a brand-new, all-NULL
column.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0045_user_avatar"
down_revision = "0044_cleanup_orphan_email_idx"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("avatar_document_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_users_avatar_document_id", "users", "documents", ["avatar_document_id"], ["id"], postgresql_not_valid=True
    )


def downgrade():
    op.drop_constraint("fk_users_avatar_document_id", "users", type_="foreignkey")
    op.drop_column("users", "avatar_document_id")
