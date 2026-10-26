"""workflow step due dates and escalation targets

Revision ID: 0052_workflow_sla_escalation
Revises: 0051_wfm_leave_cancelled
Create Date: 2026-10-26

Closes the backend gaps documented in docs/WORKFLOW_APPROVAL_GAPS.md
and docs/WORKFLOW_BUILDER_GAPS.md: no stored step due date, no
escalation target on a step, no record that an instance was escalated.
All four columns are nullable, so existing rows and definitions are
unaffected (no timeout and no target means exactly the old behaviour).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0052_workflow_sla_escalation"
down_revision = "0051_wfm_leave_cancelled"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("workflow_steps", sa.Column("escalate_to_user_id", UUID(as_uuid=True), nullable=True))
    op.add_column(
        "workflow_steps",
        sa.Column("escalate_to_role_id", UUID(as_uuid=True), sa.ForeignKey("roles.id"), nullable=True),
    )
    op.add_column("workflow_instances", sa.Column("step_due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("workflow_instances", sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_workflow_instances_step_due_at", "workflow_instances", ["step_due_at"])


def downgrade():
    op.drop_index("ix_workflow_instances_step_due_at", table_name="workflow_instances")
    op.drop_column("workflow_instances", "escalated_at")
    op.drop_column("workflow_instances", "step_due_at")
    op.drop_column("workflow_steps", "escalate_to_role_id")
    op.drop_column("workflow_steps", "escalate_to_user_id")
