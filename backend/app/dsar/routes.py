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
from marshmallow import ValidationError

from app.dsar import services
from app.dsar.models import DSARRequest
from app.dsar.schemas import (
    DSAREraseSchema,
    DSARRequestInputSchema,
    DSARRequestSchema,
    DSARRequestUpdateSchema,
)
from app.utils.pagination import envelope

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
    if table == "scp_portal_users":
        return f"Subcontractor portal user: {row.email}"
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


# --- Request tracking + erasure (permission: dsar:manage) ---------------------------

request_schema = DSARRequestSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_request_or_404(request_id) -> DSARRequest:
    req = DSARRequest.query.filter_by(id=request_id, tenant_id=g.tenant_id).first()
    if not req:
        raise APIError("DSAR request not found", status=404)
    return req


@bp.post("/requests")
@require_permission("dsar:manage")
def create_request():
    data = _load(DSARRequestInputSchema())
    req = services.create_request(g.tenant_id, user_id=g.user_id, **data)
    return jsonify(request_schema.dump(req)), 201


@bp.get("/requests")
@require_permission("dsar:manage")
def list_requests():
    q = DSARRequest.query.filter_by(tenant_id=g.tenant_id)
    status = request.args.get("status")
    if status:
        q = q.filter_by(status=status)
    reqs = q.order_by(DSARRequest.due_at.asc()).all()
    return jsonify(envelope(request_schema.dump(reqs, many=True)))


@bp.get("/requests/<uuid:request_id>")
@require_permission("dsar:manage")
def get_request(request_id):
    return jsonify(request_schema.dump(_get_request_or_404(request_id)))


@bp.patch("/requests/<uuid:request_id>")
@require_permission("dsar:manage")
def update_request(request_id):
    req = _get_request_or_404(request_id)
    data = _load(DSARRequestUpdateSchema())
    req = services.update_request(req, user_id=g.user_id, **data)
    return jsonify(request_schema.dump(req))


@bp.post("/requests/<uuid:request_id>/erase")
@require_permission("dsar:manage")
def erase(request_id):
    """Anonymises the given search-result records for an erasure
    request. Ids only are logged on the request."""
    req = _get_request_or_404(request_id)
    data = _load(DSAREraseSchema())
    records = [{"table": r["table"], "id": r["id"]} for r in data["records"]]
    req = services.erase_records(g.tenant_id, req, user_id=g.user_id, records=records)
    return jsonify(request_schema.dump(req))
