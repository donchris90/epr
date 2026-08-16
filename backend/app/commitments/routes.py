"""
Commitment accounting. Base path: /v1/commitments

Read-only by design -- this module has nothing to write. Every number
it returns is computed live from PurchaseOrder/PurchaseOrderLine data
that other modules already own and write to.
"""
from flask import Blueprint, g, jsonify

from app.commitments import services
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.commitments.schemas import CommitmentSummarySchema

bp = Blueprint("commitments", __name__, url_prefix="/v1/commitments")

summary_schema = CommitmentSummarySchema()


@bp.get("/cbs-line-items/<uuid:cbs_line_item_id>/summary")
@require_permission("fin:read")
def get_commitment_summary(cbs_line_item_id):
    summary = services.get_commitment_summary(g.tenant_id, cbs_line_item_id)
    if summary is None:
        raise APIError("CBS line item not found", status=404)
    return jsonify(summary_schema.dump(summary))
