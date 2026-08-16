"""
Module 26 -- Workflow Engine (generic, cross-module approval engine).

Not tied to any one module. Every module in this platform (Procurement,
Contracts, Tenders, Billing, Finance, HSE, ...) has been building its
own bespoke, hardcoded status-transition logic since the very first
module in this codebase -- 16 of 25 modules have some form of it, 66
separate STATUSES tuples total, none sharing any infrastructure. This
is the first genuinely shared, configurable engine: define a chain of
approval steps once, attach it to any entity in any module by
(module_name, entity_type), and every subsequent submission of that
entity type walks the same configured chain.

Deliberately scoped honestly, not pretending to be the full spec this
was requested against. What's real here: sequential steps, parallel
steps (same step_number, all must approve), amount-based step
skipping, specific-user and specific-role approver resolution,
reject-to-step (send back to an earlier step) or terminal rejection,
delegation, and a fully immutable action audit trail (old status, new
status, actor, IP, user agent, reason, timestamp -- every field the
original request asked for). What's NOT here, stated plainly rather
than faked: no visual drag-and-drop builder (this is API/model-only --
a builder is a real, separate frontend project), no notifications of
any kind (this codebase has no notification system at all -- email,
in-app, or push -- to integrate with; see docs/WORKFLOW_ENGINE.md), no
automatic timeout/escalation (needs a scheduler; the pattern from
app/modules/inv/tasks.py could drive this later, not attempted here),
no "Manager"/"Department"/"CEO" dynamic approver types (this platform
has no organizational hierarchy -- no department table, no
manager/reports-to relationship anywhere -- so those approver types
have nothing real to resolve against; only "specific_user" and
"specific_role" are implemented, because those are the only two this
schema can actually answer honestly), and no mobile integration (no
real Flutter client exists in this project to integrate into).

Attachments deliberately reuse the existing Document model
(app/documents/) rather than a new WorkflowAttachment table -- this
platform already has a real, tested file-upload system; duplicating
it here would be exactly the kind of "don't reuse what exists"
mistake this module is supposed to avoid making elsewhere.
"""
import uuid

from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.extensions import db
from app.models.base import UUIDPrimaryKeyMixin, TenantMixin, AuditMixin


APPROVER_TYPES = ("specific_user", "specific_role")
INSTANCE_STATUSES = ("pending", "approved", "rejected", "cancelled")
ACTION_TYPES = ("approve", "reject", "return", "comment", "delegate", "escalate", "cancel")


class WorkflowDefinition(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """One configured approval chain for one (module_name, entity_type)
    pair -- e.g. ("prc", "purchase_request"). A tenant can define
    multiple versions over time (`version`); only one should be
    `active` per (module_name, entity_type) at once, but that's a
    business rule enforced in services.py, not a DB constraint --
    keeping old inactive versions around is deliberate, so a workflow
    already in flight under an older version keeps making sense."""

    __tablename__ = "workflow_definitions"

    module_name = db.Column(db.String(32), nullable=False, index=True)
    entity_type = db.Column(db.String(64), nullable=False, index=True)
    workflow_name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=False)
    version = db.Column(db.Integer, nullable=False, default=1)

    steps = db.relationship(
        "WorkflowStep", back_populates="workflow", cascade="all, delete-orphan",
        order_by="WorkflowStep.step_number",
    )

    __table_args__ = (
        db.Index("ix_workflow_definitions_module_entity", "tenant_id", "module_name", "entity_type"),
    )


class WorkflowStep(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """One step in a WorkflowDefinition's chain. Multiple steps sharing
    the same step_number are a parallel group -- the instance only
    advances past that step_number once every step in the group has
    approved (see services.py:_is_step_number_satisfied)."""

    __tablename__ = "workflow_steps"

    workflow_id = db.Column(UUID(as_uuid=True), db.ForeignKey("workflow_definitions.id"), nullable=False, index=True)
    step_number = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    approver_type = db.Column(db.String(32), nullable=False)

    # approver_type == "specific_user"
    specific_user_id = db.Column(UUID(as_uuid=True), nullable=True)
    # approver_type == "specific_role"
    required_role_id = db.Column(UUID(as_uuid=True), db.ForeignKey("roles.id"), nullable=True)

    # Amount-based routing: if both are set and the instance's amount
    # falls outside [minimum_amount, maximum_amount], this step is
    # skipped automatically rather than blocking on an approver it was
    # never meant to need. Either bound alone (e.g. only a minimum) is
    # also valid -- an open-ended range.
    minimum_amount = db.Column(db.Numeric(18, 2), nullable=True)
    maximum_amount = db.Column(db.Numeric(18, 2), nullable=True)

    timeout_hours = db.Column(db.Integer, nullable=True)  # recorded, not yet enforced -- see module docstring
    auto_escalate = db.Column(db.Boolean, nullable=False, default=False)  # recorded, not yet enforced
    allow_skip = db.Column(db.Boolean, nullable=False, default=False)
    parallel = db.Column(db.Boolean, nullable=False, default=False)
    # If a rejection at this step should return the instance to an
    # earlier step (for rework) rather than terminating it outright --
    # the step_number to return to. Null means reject terminates the
    # instance.
    reject_to_step = db.Column(db.Integer, nullable=True)

    workflow = db.relationship("WorkflowDefinition", back_populates="steps")

    __table_args__ = (
        db.CheckConstraint(f"approver_type IN {APPROVER_TYPES}", name="ck_workflow_steps_approver_type"),
        db.Index("ix_workflow_steps_workflow_step_number", "workflow_id", "step_number"),
    )


class WorkflowInstance(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """One running (or completed) approval, attached to exactly one
    real entity in some module via (module_name, entity_type,
    entity_id) -- a loose reference, not a foreign key, matching the
    established pattern elsewhere in this codebase (e.g. PRC's
    cbs_line_item_id) for a table meant to be referenced from every
    module without every module needing a hard schema dependency on
    this one."""

    __tablename__ = "workflow_instances"

    workflow_id = db.Column(UUID(as_uuid=True), db.ForeignKey("workflow_definitions.id"), nullable=False, index=True)
    module_name = db.Column(db.String(32), nullable=False, index=True)
    entity_type = db.Column(db.String(64), nullable=False, index=True)
    entity_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)

    status = db.Column(db.String(16), nullable=False, default="pending", index=True)
    current_step_number = db.Column(db.Integer, nullable=False, default=1)
    amount = db.Column(db.Numeric(18, 2), nullable=True)  # drives amount-based step skipping, if the entity has one
    initiated_by = db.Column(UUID(as_uuid=True), nullable=False)

    actions = db.relationship(
        "WorkflowAction", back_populates="instance", cascade="all, delete-orphan",
        order_by="WorkflowAction.created_at",
    )

    __table_args__ = (
        db.CheckConstraint(f"status IN {INSTANCE_STATUSES}", name="ck_workflow_instances_status"),
        db.Index("ix_workflow_instances_entity", "tenant_id", "module_name", "entity_type", "entity_id"),
    )


class WorkflowAction(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """Immutable log of every action taken against a WorkflowInstance --
    no update/delete route exists or should ever exist for this table.
    Captures every field the original request asked an audit trail to
    capture: old status, new status, actor, IP, browser, timestamp
    (via created_at), and reason (comment)."""

    __tablename__ = "workflow_actions"

    instance_id = db.Column(UUID(as_uuid=True), db.ForeignKey("workflow_instances.id"), nullable=False, index=True)
    step_number = db.Column(db.Integer, nullable=False)
    action_type = db.Column(db.String(16), nullable=False)
    actor_id = db.Column(UUID(as_uuid=True), nullable=False)

    old_status = db.Column(db.String(16), nullable=True)
    new_status = db.Column(db.String(16), nullable=True)
    comment = db.Column(db.Text, nullable=True)
    delegated_to = db.Column(UUID(as_uuid=True), nullable=True)  # action_type == "delegate"

    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)

    instance = db.relationship("WorkflowInstance", back_populates="actions")

    __table_args__ = (
        db.CheckConstraint(f"action_type IN {ACTION_TYPES}", name="ck_workflow_actions_action_type"),
    )
