"""
Document storage endpoints. Base path: /v1/documents

Cross-cutting infrastructure used by virtually every module (SRS
Section 5.2), the same way app/auth/ is infrastructure rather than one
of the 25 numbered modules.
"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import envelope

from app.documents import services
from app.models.core import Document
from app.documents.schemas import (
    CreateUploadRequestSchema,
    UploadRequestResponseSchema,
    DocumentSchema,
    DocumentWithUrlSchema,
)

bp = Blueprint("documents", __name__, url_prefix="/v1/documents")

document_schema = DocumentSchema()
document_with_url_schema = DocumentWithUrlSchema()
upload_request_schema = UploadRequestResponseSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_document_or_404(document_id) -> Document:
    doc = Document.query.filter_by(id=document_id, tenant_id=g.tenant_id).first()
    if not doc:
        raise APIError("Document not found", status=404)
    return doc


@bp.get("/health")
def health():
    return jsonify({"module": "documents", "name": "Document Storage", "status": "ok"})


@bp.post("/upload-request")
@require_permission("documents:write")
def create_upload_request():
    data = _load(CreateUploadRequestSchema())
    document, upload_url = services.create_upload_request(g.tenant_id, requested_by=g.user_id, **data)
    body = upload_request_schema.dump(document)
    body["upload_url"] = upload_url
    return jsonify(body), 201


@bp.post("/<uuid:document_id>/confirm")
@require_permission("documents:write")
def confirm_upload(document_id):
    document = _get_document_or_404(document_id)
    document = services.confirm_upload(document, confirmed_by=g.user_id)
    return jsonify(document_schema.dump(document))


@bp.get("/<uuid:document_id>")
@require_permission("documents:read")
def get_document(document_id):
    document = _get_document_or_404(document_id)
    body = document_with_url_schema.dump(document)
    body["download_url"] = services.get_download_url(document) if document.status == "uploaded" else None
    return jsonify(body)


@bp.get("")
@require_permission("documents:read")
def list_documents():
    project_id = request.args.get("project_id")
    doc_type = request.args.get("doc_type")
    source = request.args.get("source", "")
    query = Document.query.filter_by(tenant_id=g.tenant_id)
    if project_id:
        query = query.filter_by(project_id=project_id)
    if doc_type:
        query = query.filter_by(doc_type=doc_type)
    # source: "" = everything, "staff" = uploaded by staff, "vendor" /
    # "subcontractor" = uploaded through that portal. A specific
    # organisation can be narrowed with portal_owner_id.
    if source == "staff":
        query = query.filter(Document.portal_owner_type.is_(None))
    elif source in ("vendor", "subcontractor"):
        query = query.filter_by(portal_owner_type="vnp" if source == "vendor" else "scp")
        owner_id = request.args.get("portal_owner_id")
        if owner_id:
            import uuid

            try:
                owner_id = uuid.UUID(owner_id)
            except ValueError:
                raise APIError("portal_owner_id must be a valid id", status=400)
            query = query.filter_by(portal_owner_id=owner_id)
    elif source:
        raise APIError("Unknown source filter", status=400)
    documents = query.order_by(Document.created_at.desc()).all()
    body = document_schema.dump(documents, many=True)
    names = services.portal_owner_names(g.tenant_id, documents)
    for item, doc in zip(body, documents):
        item["source_name"] = names.get((doc.portal_owner_type, doc.portal_owner_id))
    return jsonify(envelope(body))


@bp.delete("/<uuid:document_id>")
@require_permission("documents:write")
def delete_document(document_id):
    document = _get_document_or_404(document_id)
    services.delete_document(document)
    return "", 204
