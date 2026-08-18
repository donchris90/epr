"""
Global search. Base path: /v1/search
"""
from flask import Blueprint, g, jsonify, request

from app.search import services
from app.utils.errors import APIError

bp = Blueprint("search", __name__, url_prefix="/v1/search")


@bp.get("")
def global_search():
    """No @require_permission here on purpose -- any authenticated
    tenant user can search at all, matching real search UX everywhere
    (Slack, Gmail, etc. don't gate the search box itself). What's
    actually gated, per entity type, is inside services.search: a
    caller only ever sees results from types their real permissions
    already let them read, checked the same way any other read
    endpoint in this app is.

    Still requires real authentication, checked explicitly here:
    without @require_permission there was nothing stopping an
    unauthenticated request from reaching this route at all -- it
    would have just silently returned an empty result list rather
    than a real 401, since g.tenant_id is simply None with no JWT
    present."""
    if not g.tenant_id:
        raise APIError("Authentication required", status=401)

    query = request.args.get("q", "")
    results = services.search(g.tenant_id, query=query, permissions=g.permissions)
    return jsonify({"data": results})
