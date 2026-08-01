"""workflow engine - generic cross-module approval engine

Revision ID: 0031_workflow_engine
Revises: 0030_email_tenant_index
Create Date: 2026-08-01

Module 26 -- see app/workflow/models.py for the full design scope and
honest limitations (no visual builder, no notifications, no
timeout/escalation enforcement, no org-hierarchy-based approver types,
no mobile integration -- none of that infrastructure exists elsewhere
in this codebase yet either).

All four tables are tenant-scoped and RLS-protected like every other
tenant table in this platform, ENABLE + FORCE per the standard set by
every module since migration 0002.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0031_workflow_engine"
down_revision = "0030_email_tenant_index"
branch_labels = None
depends_on = None


def _audit_columns():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", UUID(as_uuid=True), nullable=True),
    ]


def upgrade():
    op.create_table(
        "workflow_definitions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("module_name", sa.String(32), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("workflow_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        *_audit_columns(),
    )
    op.create_index("ix_workflow_definitions_tenant_id", "workflow_definitions", ["tenant_id"])
    op.create_index(
        "ix_workflow_definitions_module_entity", "workflow_definitions", ["tenant_id", "module_name", "entity_type"]
    )

    op.create_table(
        "workflow_steps",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("workflow_id", UUID(as_uuid=True), sa.ForeignKey("workflow_definitions.id"), nullable=False),
        sa.Column("step_number", sa.Integer, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("approver_type", sa.String(32), nullable=False),
        sa.Column("specific_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("required_role_id", UUID(as_uuid=True), sa.ForeignKey("roles.id"), nullable=True),
        sa.Column("minimum_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("maximum_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("timeout_hours", sa.Integer, nullable=True),
        sa.Column("auto_escalate", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("allow_skip", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("parallel", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("reject_to_step", sa.Integer, nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("approver_type IN ('specific_user', 'specific_role')", name="ck_workflow_steps_approver_type"),
    )
    op.create_index("ix_workflow_steps_tenant_id", "workflow_steps", ["tenant_id"])
    op.create_index("ix_workflow_steps_workflow_id", "workflow_steps", ["workflow_id"])
    op.create_index("ix_workflow_steps_workflow_step_number", "workflow_steps", ["workflow_id", "step_number"])

    op.create_table(
        "workflow_instances",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("workflow_id", UUID(as_uuid=True), sa.ForeignKey("workflow_definitions.id"), nullable=False),
        sa.Column("module_name", sa.String(32), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("current_step_number", sa.Integer, nullable=False, server_default="1"),
        sa.Column("amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("initiated_by", UUID(as_uuid=True), nullable=False),
        *_audit_columns(),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')", name="ck_workflow_instances_status"
        ),
    )
    op.create_index("ix_workflow_instances_tenant_id", "workflow_instances", ["tenant_id"])
    op.create_index("ix_workflow_instances_workflow_id", "workflow_instances", ["workflow_id"])
    op.create_index("ix_workflow_instances_module_name", "workflow_instances", ["module_name"])
    op.create_index("ix_workflow_instances_entity_type", "workflow_instances", ["entity_type"])
    op.create_index("ix_workflow_instances_entity_id", "workflow_instances", ["entity_id"])
    op.create_index("ix_workflow_instances_status", "workflow_instances", ["status"])
    op.create_index(
        "ix_workflow_instances_entity",
        "workflow_instances",
        ["tenant_id", "module_name", "entity_type", "entity_id"],
    )

    op.create_table(
        "workflow_actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("instance_id", UUID(as_uuid=True), sa.ForeignKey("workflow_instances.id"), nullable=False),
        sa.Column("step_number", sa.Integer, nullable=False),
        sa.Column("action_type", sa.String(16), nullable=False),
        sa.Column("actor_id", UUID(as_uuid=True), nullable=False),
        sa.Column("old_status", sa.String(16), nullable=True),
        sa.Column("new_status", sa.String(16), nullable=True),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("delegated_to", UUID(as_uuid=True), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(
            "action_type IN ('approve', 'reject', 'return', 'comment', 'delegate', 'escalate', 'cancel')",
            name="ck_workflow_actions_action_type",
        ),
    )
    op.create_index("ix_workflow_actions_tenant_id", "workflow_actions", ["tenant_id"])
    op.create_index("ix_workflow_actions_instance_id", "workflow_actions", ["instance_id"])

    for table in ("workflow_definitions", "workflow_steps", "workflow_instances", "workflow_actions"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            """
        )


def downgrade():
    for table in ("workflow_actions", "workflow_instances", "workflow_steps", "workflow_definitions"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
    op.drop_table("workflow_actions")
    op.drop_table("workflow_instances")
    op.drop_table("workflow_steps")
    op.drop_table("workflow_definitions")
