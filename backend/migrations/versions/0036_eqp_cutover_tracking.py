"""eqp equipment transfer cutover tracking

Revision ID: 0036_eqp_cutover_tracking
Revises: 0035_prc_inventory_link
Create Date: 2026-08-15

Adds cutover_applied_at to eqp_equipment_transfers -- tracks whether
the real effect of a transfer (equipment.current_project_id switching)
has actually happened yet, distinct from `status` staying "approved"
regardless of whether that's true. Closes a real, previously-documented
gap: a future-dated transfer's cutover was never applied by anything
once the approval itself was recorded -- the code's own comment said
"this module has no Celery task wired up yet." See
app/modules/eqp/tasks.py for the task this enables.
"""
from alembic import op
import sqlalchemy as sa

revision = "0036_eqp_cutover_tracking"
down_revision = "0035_prc_inventory_link"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "eqp_equipment_transfers",
        sa.Column("cutover_applied_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Backfill: every existing approved transfer with a cutover_date in
    # the past or today has, under the pre-existing logic, already had
    # its cutover applied at approval time (approve_transfer always
    # applied same-day-or-earlier cutovers immediately) -- mark those
    # as applied now so the new Celery task doesn't try to re-apply
    # them and get a confusing "already applied but tracked as not"
    # state for data that predates this column existing.
    #
    # Loops per-tenant rather than one bare UPDATE scanning every
    # tenant at once -- eqp_equipment_transfers has FORCE ROW LEVEL
    # SECURITY, and this migration runs through the same single
    # production role as everything else; a cross-tenant UPDATE with
    # no app.tenant_id ever set hits the exact wall documented at
    # length in migration 0030_email_tenant_index.py. tenants itself
    # has no RLS at all, so it's safe to enumerate directly.
    connection = op.get_bind()
    tenant_ids = [row[0] for row in connection.execute(sa.text("SELECT id FROM tenants")).fetchall()]
    for tenant_id in tenant_ids:
        connection.execute(sa.text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})
        connection.execute(
            sa.text(
                """
                UPDATE eqp_equipment_transfers
                SET cutover_applied_at = COALESCE(approved_at, now())
                WHERE tenant_id = :tid AND status = 'approved' AND cutover_date <= CURRENT_DATE
                """
            ),
            {"tid": str(tenant_id)},
        )


def downgrade():
    op.drop_column("eqp_equipment_transfers", "cutover_applied_at")
