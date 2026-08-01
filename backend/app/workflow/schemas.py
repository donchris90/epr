from marshmallow import Schema, fields, validate

from app.workflow.models import APPROVER_TYPES, INSTANCE_STATUSES, ACTION_TYPES


class WorkflowStepInputSchema(Schema):
    step_number = fields.Int(required=True)
    name = fields.Str(required=True)
    approver_type = fields.Str(required=True, validate=validate.OneOf(APPROVER_TYPES))
    specific_user_id = fields.UUID(allow_none=True)
    required_role_id = fields.UUID(allow_none=True)
    minimum_amount = fields.Decimal(allow_none=True, as_string=True)
    maximum_amount = fields.Decimal(allow_none=True, as_string=True)
    timeout_hours = fields.Int(allow_none=True)
    auto_escalate = fields.Bool(load_default=False)
    allow_skip = fields.Bool(load_default=False)
    parallel = fields.Bool(load_default=False)
    reject_to_step = fields.Int(allow_none=True)


class WorkflowStepSchema(WorkflowStepInputSchema):
    id = fields.UUID(dump_only=True)


class WorkflowDefinitionInputSchema(Schema):
    module_name = fields.Str(required=True)
    entity_type = fields.Str(required=True)
    workflow_name = fields.Str(required=True)
    description = fields.Str(allow_none=True)
    steps = fields.List(fields.Nested(WorkflowStepInputSchema), required=True)


class WorkflowDefinitionSchema(Schema):
    id = fields.UUID(dump_only=True)
    module_name = fields.Str(dump_only=True)
    entity_type = fields.Str(dump_only=True)
    workflow_name = fields.Str(dump_only=True)
    description = fields.Str(dump_only=True)
    active = fields.Bool(dump_only=True)
    version = fields.Int(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    steps = fields.List(fields.Nested(WorkflowStepSchema), dump_only=True)


class WorkflowActionSchema(Schema):
    id = fields.UUID(dump_only=True)
    step_number = fields.Int(dump_only=True)
    action_type = fields.Str(dump_only=True)
    actor_id = fields.UUID(dump_only=True)
    old_status = fields.Str(dump_only=True)
    new_status = fields.Str(dump_only=True)
    comment = fields.Str(dump_only=True)
    delegated_to = fields.UUID(dump_only=True)
    created_at = fields.DateTime(dump_only=True)


class WorkflowInstanceSchema(Schema):
    id = fields.UUID(dump_only=True)
    workflow_id = fields.UUID(dump_only=True)
    module_name = fields.Str(dump_only=True)
    entity_type = fields.Str(dump_only=True)
    entity_id = fields.UUID(dump_only=True)
    status = fields.Str(dump_only=True, validate=validate.OneOf(INSTANCE_STATUSES))
    current_step_number = fields.Int(dump_only=True)
    amount = fields.Decimal(dump_only=True, as_string=True)
    initiated_by = fields.UUID(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    actions = fields.List(fields.Nested(WorkflowActionSchema), dump_only=True)


class StartWorkflowInstanceSchema(Schema):
    module_name = fields.Str(required=True)
    entity_type = fields.Str(required=True)
    entity_id = fields.UUID(required=True)
    amount = fields.Decimal(allow_none=True, as_string=True)


class WorkflowDecisionSchema(Schema):
    comment = fields.Str(allow_none=True)


class WorkflowDelegateSchema(Schema):
    delegate_to = fields.UUID(required=True)
    comment = fields.Str(allow_none=True)
