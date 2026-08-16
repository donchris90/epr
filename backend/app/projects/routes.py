"""
Cross-cutting Project listing. Base path: /v1/projects

Read-only by design -- project creation/lifecycle is out of scope
here and stays wherever it already lives (this route only lists what
already exists), matching commitments' own "nothing to write" pattern.
"""
from flask import Blueprint, g, jsonify, request

from app.projects import services
from app.projects.schemas import ProjectSchema
from app.utils.decorators import require_permission
from app.utils.pagination import envelope

bp = Blueprint("projects", __name__, url_prefix="/v1/projects")

project_schema = ProjectSchema()


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
