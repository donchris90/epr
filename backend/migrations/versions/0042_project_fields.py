"""project client/pm/dates

Revision ID: 0042_project_fields
Revises: 0041_invite_token_idx
Create Date: 2026-08-18

Real, foundational fields for a proper Projects list/workspace
(previously the Project model only had name/status -- genuinely
minimal). client_id and project_manager_id are nullable: a project
can exist before either is assigned, matching real construction
practice (a project might be created ahead of a finalized client
contract or PM assignment).

Deliberately NOT adding budget/actual_cost/progress columns here --
those are real, computed rollups that belong to the modules that
actually own that data (EST for budget baselines, PC/finance for
actual cost, EXE for progress), not duplicated onto Project itself.
Aggregating them is real, separate, larger work.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0042_project_fields"
down_revision = "0041_invite_token_idx"
branch_labels = None
depends_on = None


def upgrade():
    # Added without an inline ForeignKey, then created separately as
    # NOT VALID below -- an inline FK triggers Postgres to validate
    # existing rows against the referenced table immediately, and
    # that validation query fails with no app.tenant_id set (both
    # bdc_clients and users have FORCE RLS). Safe here regardless:
    # these are brand-new columns, every existing row has NULL in
    # them, so there is nothing to violate.
    op.add_column("projects", sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("projects", sa.Column("project_manager_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("projects", sa.Column("start_date", sa.Date(), nullable=True))
    op.add_column("projects", sa.Column("end_date", sa.Date(), nullable=True))

    op.create_foreign_key(
        "fk_projects_client_id", "projects", "bdc_clients", ["client_id"], ["id"], postgresql_not_valid=True
    )
    op.create_foreign_key(
        "fk_projects_project_manager_id", "projects", "users", ["project_manager_id"], ["id"], postgresql_not_valid=True
    )


def downgrade():
    op.drop_constraint("fk_projects_project_manager_id", "projects", type_="foreignkey")
    op.drop_constraint("fk_projects_client_id", "projects", type_="foreignkey")
    op.drop_column("projects", "end_date")
    op.drop_column("projects", "start_date")
    op.drop_column("projects", "project_manager_id")
    op.drop_column("projects", "client_id")
