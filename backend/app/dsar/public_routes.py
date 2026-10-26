"""
Public privacy-request form. Base path: /v1/public/privacy/<tenant_id>

Unauthenticated by design: a person asking a company what data it holds
about them has no account. The tenant is named by the link the company
publishes (its id), the requester's email is verified by a confirmation
link before staff act on the request, and the endpoint is rate limited
and honeypotted since it creates rows without a login.
"""
from flask import Blueprint, current_app, g, jsonify, request
from marshmallow import ValidationError
from sqlalchemy import text

from app.dsar import services
from app.dsar.schemas import PublicDSARRequestSchema, PublicVerifySchema
from app.extensions import db, limiter
from app.models.core import Tenant
from app.utils.errors import APIError

bp = Blueprint("dsar_public", __name__, url_prefix="/v1/public/privacy")


def _tenant_or_404(tenant_id) -> Tenant:
    tenant = db.session.get(Tenant, tenant_id)
    if not tenant or tenant.is_suspended:
        raise APIError("Not found", status=404)
    # No JWT here, so set the tenant context the middleware would have.
    g.tenant_id = str(tenant.id)
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant.id)})
    return tenant


def _load(schema):
    try:
        return schema.load(request.get_json(force=True, silent=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


@bp.get("/<uuid:tenant_id>")
@limiter.limit("60 per hour")
def preview(tenant_id):
    tenant = _tenant_or_404(tenant_id)
    return jsonify({"company_name": tenant.name, "response_days": services.RESPONSE_DAYS})


@bp.post("/<uuid:tenant_id>/requests")
@limiter.limit("5 per hour")
def submit(tenant_id):
    tenant = _tenant_or_404(tenant_id)
    data = _load(PublicDSARRequestSchema())
    if data.pop("website"):
        # Honeypot tripped: pretend success, store nothing.
        return jsonify({"received": True}), 201
    services.submit_public_request(tenant, frontend_url=current_app.config.get("FRONTEND_URL", ""), **data)
    # Identical whether created or de-duplicated.
    return jsonify({"received": True, "response_days": services.RESPONSE_DAYS}), 201


@bp.post("/<uuid:tenant_id>/verify")
@limiter.limit("20 per hour")
def verify(tenant_id):
    _tenant_or_404(tenant_id)
    data = _load(PublicVerifySchema())
    services.verify_public_request(tenant_id, data["token"])
    return jsonify({"verified": True})
