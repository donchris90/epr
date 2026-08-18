"""
Cross-cutting Project listing and lifecycle. Base path: /v1/projects

Reading (projects:read) is broader than creating/editing
(projects:manage), matching the same pattern used across this
codebase (billing, org).
"""
from flask import Blueprint, g, jsonify, request

from app.projects import services
from app.projects.schemas import ProjectSchema, ProjectDetailSchema, CreateProjectSchema, UpdateProjectSchema
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import envelope

bp = Blueprint("projects", __name__, url_prefix="/v1/projects")

project_schema = ProjectSchema()
detail_schema = ProjectDetailSchema()


def _load(schema):
    data = request.get_json(force=True) or {}
    errors = schema.validate(data)
    if errors:
        raise APIError("Validation failed", status=400, detail=str(errors))
    return schema.load(data)


@bp.get("")
@require_permission("projects:read")
def list_projects():
    """Real project selection, replacing raw UUID-paste fields across
    the frontend and mobile app -- optional ?search= (name, partial
    match) and ?status= (exact) query params, for the same searchable-
    selector use case the master audit called out."""
    projects = services.list_projects(
        g.tenant_id,
        search=request.args.get("search"),
        status=request.args.get("status"),
    )
    return jsonify(envelope(project_schema.dump(projects, many=True)))


@bp.post("")
@require_permission("projects:manage")
def create_project():
    data = _load(CreateProjectSchema())
    project = services.create_project(
        g.tenant_id,
        company_id=data["company_id"],
        name=data["name"],
        client_id=data.get("client_id"),
        project_manager_id=data.get("project_manager_id"),
        start_date=data.get("start_date"),
        end_date=data.get("end_date"),
    )
    return jsonify(project_schema.dump(project)), 201


@bp.get("/<uuid:project_id>")
@require_permission("projects:read")
def get_project(project_id):
    detail = services.get_project_detail(g.tenant_id, project_id)
    body = detail_schema.dump(detail["project"])
    body["client_name"] = detail["client_name"]
    body["contract_value"] = str(detail["contract_value"]) if detail["contract_value"] is not None else None
    body["currency"] = detail["currency"]
    return jsonify(body)


@bp.put("/<uuid:project_id>")
@require_permission("projects:manage")
def update_project(project_id):
    """Known, deliberate limitation: client_id/project_manager_id can
    be SET here but not explicitly CLEARED (a request that omits the
    field and one that sends it as null are indistinguishable through
    a plain dict.get()) -- fine for the real, common case (assigning a
    client/PM), not yet built out for "unassign" flows. Worth a real,
    small follow-up (a sentinel value or a separate unassign endpoint)
    if that need comes up, not solved here under time pressure with a
    half-considered fix."""
    data = _load(UpdateProjectSchema())
    project = services.update_project(
        g.tenant_id, project_id,
        name=data.get("name"), client_id=data.get("client_id"), project_manager_id=data.get("project_manager_id"),
        start_date=data.get("start_date"), end_date=data.get("end_date"), status=data.get("status"),
    )
    return jsonify(project_schema.dump(project))
