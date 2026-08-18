from marshmallow import Schema, fields, validate


class ProjectSchema(Schema):
    id = fields.UUID(dump_only=True)
    company_id = fields.UUID(dump_only=True)
    contract_id = fields.UUID(dump_only=True, allow_none=True)
    client_id = fields.UUID(dump_only=True, allow_none=True)
    project_manager_id = fields.UUID(dump_only=True, allow_none=True)
    name = fields.Str(dump_only=True)
    status = fields.Str(dump_only=True)
    start_date = fields.Date(dump_only=True, allow_none=True)
    end_date = fields.Date(dump_only=True, allow_none=True)


class ProjectDetailSchema(Schema):
    """Real fields only -- deliberately no budget/actual_cost/progress
    here (see app/projects/services.py:get_project_detail's own
    docstring on why those aren't faked)."""
    id = fields.UUID(dump_only=True)
    name = fields.Str(dump_only=True)
    status = fields.Str(dump_only=True)
    client_id = fields.UUID(dump_only=True, allow_none=True)
    client_name = fields.Str(dump_only=True, allow_none=True)
    project_manager_id = fields.UUID(dump_only=True, allow_none=True)
    start_date = fields.Date(dump_only=True, allow_none=True)
    end_date = fields.Date(dump_only=True, allow_none=True)
    contract_value = fields.Decimal(dump_only=True, allow_none=True, as_string=True)
    currency = fields.Str(dump_only=True, allow_none=True)


class CreateProjectSchema(Schema):
    company_id = fields.UUID(required=True)
    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    client_id = fields.UUID(required=False, allow_none=True)
    project_manager_id = fields.UUID(required=False, allow_none=True)
    start_date = fields.Date(required=False, allow_none=True)
    end_date = fields.Date(required=False, allow_none=True)


class UpdateProjectSchema(Schema):
    name = fields.Str(required=False, validate=validate.Length(min=1, max=255))
    client_id = fields.UUID(required=False, allow_none=True)
    project_manager_id = fields.UUID(required=False, allow_none=True)
    start_date = fields.Date(required=False, allow_none=True)
    end_date = fields.Date(required=False, allow_none=True)
    status = fields.Str(required=False, validate=validate.OneOf(["active", "completed", "on_hold", "archived"]))
