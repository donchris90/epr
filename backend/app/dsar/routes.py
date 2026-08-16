"""
DSAR search. Base path: /v1/dsar

Requires the "dsar:search" permission specifically -- not folded into
a general admin/read permission, because "search for a named
individual's data across every module" is a meaningfully different,
more sensitive capability than any single module's own read access,
and should be grantable (or auditable) independently of it.
"""
from flask import Blueprint, g, jsonify, request

from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.dsar import services

bp = Blueprint("dsar", __name__, url_prefix="/v1/dsar")


def _summarize(table: str, row) -> str:
    """A short, human-readable line identifying the record -- enough
    for an operator to know what they're looking at and go open the
    real record through its own module, not a substitute for that."""
    if table == "users":
        return f"Internal user: {row.email}"
    if table == "bdc_clients":
        return f"BDC client: {row.name}"
    if table == "bdc_contacts":
        return f"BDC contact: {row.name} ({row.email or row.phone})"
    if table == "wfm_casual_workers":
        return f"Casual worker: {row.name} ({row.id_number or 'no ID number'})"
    if table == "clp_portal_users":
        return f"Client portal user: {row.email} ({row.client_organization_name})"
    if table == "vnp_portal_users":
        return f"Vendor portal user: {row.email}"
    return f"{table} record"


@bp.get("/search")
@require_permission("dsar:search")
def search():
    email = request.args.get("email")
    phone = request.args.get("phone")

    if not email and not phone:
        raise APIError("At least one of email or phone is required", status=400)

    result = services.search_by_identifier(g.tenant_id, email=email, phone=phone)

    serialized = {
        table: [{"id": str(row.id), "table": table, "summary": _summarize(table, row)} for row in rows]
        for table, rows in result["results"].items()
    }

    return jsonify({"query": result["query"], "results": serialized, "total_matches": result["total_matches"]})
