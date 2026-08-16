"""
Workflow Engine. Base path: /v1/workflow

Two permission families, deliberately separate: "workflow:admin" for
defining/activating chains (a platform-configuration action, not
something every approver should be able to do), and "workflow:approve"
for actually acting on an instance an approver has been routed. A
tenant can grant one without the other.
"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import envelope

from app.workflow import services
from app.workflow.models import WorkflowDefinition, WorkflowInstance
from app.workflow.schemas import (
    WorkflowDefinitionInputSchema,
    WorkflowDefinitionSchema,
    WorkflowInstanceSchema,
    StartWorkflowInstanceSchema,
    WorkflowDecisionSchema,
    WorkflowDelegateSchema,
)

bp = Blueprint("workflow", __name__, url_prefix="/v1/workflow")

definition_schema = WorkflowDefinitionSchema()
instance_schema = WorkflowInstanceSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _client_context():
    return {
        "ip_address": request.headers.get("X-Forwarded-For", request.remote_addr),
        "user_agent": request.headers.get("User-Agent"),
    }


# --- Definitions ------------------------------------------------------------

@bp.post("/definitions")
@require_permission("workflow:admin")
def create_definition():
    data = _load(WorkflowDefinitionInputSchema())
    definition = services.create_workflow_definition(
        g.tenant_id,
        module_name=data["module_name"],
        entity_type=data["entity_type"],
        workflow_name=data["workflow_name"],
        description=data.get("description"),
        steps=data["steps"],
        created_by=g.user_id,
    )
    return jsonify(definition_schema.dump(definition)), 201


@bp.get("/definitions")
@require_permission("workflow:admin")
def list_definitions():
    query = WorkflowDefinition.query.filter_by(tenant_id=g.tenant_id)
    module_name = request.args.get("module_name")
    entity_type = request.args.get("entity_type")
    if module_name:
        query = query.filter_by(module_name=module_name)
    if entity_type:
        query = query.filter_by(entity_type=entity_type)
    items = query.order_by(WorkflowDefinition.created_at.desc()).all()
    return jsonify(envelope(definition_schema.dump(items, many=True)))


@bp.get("/definitions/<uuid:definition_id>")
@require_permission("workflow:admin")
def get_definition(definition_id):
    definition = WorkflowDefinition.query.filter_by(id=definition_id, tenant_id=g.tenant_id).first()
    if not definition:
        raise APIError("Workflow definition not found", status=404)
    return jsonify(definition_schema.dump(definition))


@bp.post("/definitions/<uuid:definition_id>/activate")
@require_permission("workflow:admin")
def activate_definition(definition_id):
    definition = WorkflowDefinition.query.filter_by(id=definition_id, tenant_id=g.tenant_id).first()
    if not definition:
        raise APIError("Workflow definition not found", status=404)
    definition = services.activate_workflow_definition(definition)
    return jsonify(definition_schema.dump(definition))


@bp.post("/definitions/<uuid:definition_id>/deactivate")
@require_permission("workflow:admin")
def deactivate_definition(definition_id):
    definition = WorkflowDefinition.query.filter_by(id=definition_id, tenant_id=g.tenant_id).first()
    if not definition:
        raise APIError("Workflow definition not found", status=404)
    definition = services.deactivate_workflow_definition(definition)
    return jsonify(definition_schema.dump(definition))


# --- Instances ---------------------------------------------------------------

@bp.post("/instances")
@require_permission("workflow:approve")
def start_instance():
    """Generic entry point any module can call once it has an
    entity_id and (optionally) an amount -- see
    app/modules/prc/services.py's real integration for the pattern a
    module actually adopts this with."""
    data = _load(StartWorkflowInstanceSchema())
    workflow = services.get_active_workflow(g.tenant_id, module_name=data["module_name"], entity_type=data["entity_type"])
    if not workflow:
        raise APIError("No active workflow configured for this module/entity type", status=404)

    instance = services.start_workflow_instance(
        g.tenant_id, workflow,
        module_name=data["module_name"], entity_type=data["entity_type"], entity_id=data["entity_id"],
        initiated_by=g.user_id, amount=data.get("amount"),
    )
    return jsonify(instance_schema.dump(instance)), 201


@bp.get("/instances/pending")
@require_permission("workflow:approve")
def list_pending_approvals():
    instances = services.get_pending_approvals_for_user(g.tenant_id, user_id=g.user_id, role_id=g.role_id)
    return jsonify(envelope(instance_schema.dump(instances, many=True)))


@bp.get("/instances")
@require_permission("workflow:approve")
def list_instances():
    """Filterable history/search -- module, entity_type, status are
    the filters explicitly asked for that this schema can actually
    answer (requester/approver/date/amount filtering would need a
    join against WorkflowAction and real query-building; left as a
    follow-up, not faked here)."""
    query = WorkflowInstance.query.filter_by(tenant_id=g.tenant_id)
    for field in ("module_name", "entity_type", "status"):
        value = request.args.get(field)
        if value:
            query = query.filter_by(**{field: value})
    items = query.order_by(WorkflowInstance.created_at.desc()).limit(200).all()
    return jsonify(envelope(instance_schema.dump(items, many=True)))


@bp.get("/instances/<uuid:instance_id>")
@require_permission("workflow:approve")
def get_instance(instance_id):
    instance = WorkflowInstance.query.filter_by(id=instance_id, tenant_id=g.tenant_id).first()
    if not instance:
        raise APIError("Workflow instance not found", status=404)
    return jsonify(instance_schema.dump(instance))


@bp.post("/instances/<uuid:instance_id>/approve")
@require_permission("workflow:approve")
def approve_instance(instance_id):
    instance = WorkflowInstance.query.filter_by(id=instance_id, tenant_id=g.tenant_id).first()
    if not instance:
        raise APIError("Workflow instance not found", status=404)
    data = _load(WorkflowDecisionSchema())
    instance = services.approve_step(
        instance, actor_id=g.user_id, role_id=g.role_id, comment=data.get("comment"), **_client_context()
    )
    return jsonify(instance_schema.dump(instance))


@bp.post("/instances/<uuid:instance_id>/reject")
@require_permission("workflow:approve")
def reject_instance(instance_id):
    instance = WorkflowInstance.query.filter_by(id=instance_id, tenant_id=g.tenant_id).first()
    if not instance:
        raise APIError("Workflow instance not found", status=404)
    data = _load(WorkflowDecisionSchema())
    instance = services.reject_step(
        instance, actor_id=g.user_id, role_id=g.role_id, comment=data.get("comment"), **_client_context()
    )
    return jsonify(instance_schema.dump(instance))


@bp.post("/instances/<uuid:instance_id>/delegate")
@require_permission("workflow:approve")
def delegate_instance(instance_id):
    instance = WorkflowInstance.query.filter_by(id=instance_id, tenant_id=g.tenant_id).first()
    if not instance:
        raise APIError("Workflow instance not found", status=404)
    data = _load(WorkflowDelegateSchema())
    instance = services.delegate_step(
        instance, actor_id=g.user_id, role_id=g.role_id,
        delegate_to=data["delegate_to"], comment=data.get("comment"), **_client_context()
    )
    return jsonify(instance_schema.dump(instance))


@bp.post("/instances/<uuid:instance_id>/cancel")
@require_permission("workflow:approve")
def cancel_instance_route(instance_id):
    instance = WorkflowInstance.query.filter_by(id=instance_id, tenant_id=g.tenant_id).first()
    if not instance:
        raise APIError("Workflow instance not found", status=404)
    data = _load(WorkflowDecisionSchema())
    instance = services.cancel_instance(instance, actor_id=g.user_id, comment=data.get("comment"), **_client_context())
    return jsonify(instance_schema.dump(instance))


@bp.post("/instances/<uuid:instance_id>/comment")
@require_permission("workflow:approve")
def comment_instance(instance_id):
    instance = WorkflowInstance.query.filter_by(id=instance_id, tenant_id=g.tenant_id).first()
    if not instance:
        raise APIError("Workflow instance not found", status=404)
    data = _load(WorkflowDecisionSchema())
    if not data.get("comment"):
        raise APIError("comment is required", status=400)
    instance = services.add_comment(instance, actor_id=g.user_id, comment=data["comment"], **_client_context())
    return jsonify(instance_schema.dump(instance))
