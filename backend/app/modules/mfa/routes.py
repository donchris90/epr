"""
Module 24 — Mobile Field App (Code: MFA)
SRS Section 4.24 — Flask Blueprint. Base path: /v1/mfa
"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import envelope

from app.modules.mfa import services
from app.modules.mfa.models import ConflictRecord
from app.modules.mfa.schemas import (
    SyncBatchInputSchema,
    SyncQueueEntrySchema,
    ResolveConflictSchema,
    ConflictRecordSchema,
)

bp = Blueprint("mfa", __name__, url_prefix="/v1/mfa")

sync_entry_schema = SyncQueueEntrySchema()
conflict_schema = ConflictRecordSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_conflict_or_404(conflict_id) -> ConflictRecord:
    c = ConflictRecord.query.filter_by(id=conflict_id, tenant_id=g.tenant_id).first()
    if not c:
        raise APIError("Conflict record not found", status=404)
    return c


@bp.get("/health")
def health():
    return jsonify({"module": "mfa", "name": "Mobile Field App", "status": "ok"})


# --- Sync (MFA-08, MFA-09, business rules) ------------------------------------------

@bp.post("/sync-batch")
@require_permission("mfa:write")
def submit_sync_batch():
    """The core offline-sync endpoint: a device posts a batch of
    locally-captured records; each is either applied (status=synced)
    or surfaced as a conflict, never silently dropped."""
    data = _load(SyncBatchInputSchema())
    results = services.submit_sync_batch(g.tenant_id, **data)
    return jsonify(envelope(sync_entry_schema.dump(results, many=True))), 201


@bp.get("/sync-status")
@require_permission("mfa:read")
def get_sync_status():
    device_id = request.args.get("device_id")
    summary = services.get_sync_status_summary(g.tenant_id, device_id=device_id)
    return jsonify(summary)


# --- Conflicts (business rule) -----------------------------------------------------

@bp.get("/conflicts")
@require_permission("mfa:read")
def list_conflicts():
    status = request.args.get("status", "unresolved")
    conflicts = ConflictRecord.query.filter_by(tenant_id=g.tenant_id, status=status).all()
    return jsonify(envelope(conflict_schema.dump(conflicts, many=True)))


@bp.post("/conflicts/<uuid:conflict_id>/resolve")
@require_permission("mfa:approve")
def resolve_conflict(conflict_id):
    conflict = _get_conflict_or_404(conflict_id)
    data = _load(ResolveConflictSchema())
    conflict = services.resolve_conflict(conflict, resolved_by=g.user_id, **data)
    return jsonify(conflict_schema.dump(conflict))
