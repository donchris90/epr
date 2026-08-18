"""invitation token index

Revision ID: 0041_invite_token_idx
Revises: 0040_org_invitations
Create Date: 2026-08-17

Real bug found during testing, not by inspection: invitations has
FORCE RLS (correctly, for the authenticated admin-facing routes --
list/create/cancel/resend all have real tenant context and should
stay RLS-protected). But the public accept-invitation flow
(GET /v1/org/invitations/preview, POST /v1/org/invitations/accept)
looks up an invitation BY TOKEN before the caller has any tenant
context at all -- discovering which tenant it belongs to is the whole
point of the lookup. RLS requires app.tenant_id to already be set to
return any row, so that lookup returned nothing for every token,
every time, regardless of validity.

Exactly the same structural problem EmailTenantIndex
(app/models/core.py) already solves for login, applied here: a
separate, deliberately NOT tenant-scoped, NOT RLS-protected table
whose only job is resolving token_hash -> tenant_id so real tenant
context can be established BEFORE querying the real (RLS-protected)
invitations table for the full, validated row.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0041_invite_token_idx"
down_revision = "0040_org_invitations"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "invitation_token_index",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("invitation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # Deliberately NO RLS enabled here -- see this migration's own
    # docstring for exactly why.


def downgrade():
    op.drop_table("invitation_token_index")
