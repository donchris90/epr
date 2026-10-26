"""
Document upload / list / download for external portal users
(subcontractor "scp" and vendor "vnp"). Portal tokens do not hold the
tenant-wide `documents:*` permissions and should not, so these helpers
sit beside the staff flow (app/documents/services.py), which they reuse
for the actual S3 work.

Scoping: every document is stamped with the owning organisation
(`portal_owner_type` + `portal_owner_id` = subcontractor_id / vendor_id).
A portal user can only list, confirm or download documents stamped with
their own organisation; anything else is a 404, not a 403, so ids do not
leak. Colleagues in the same organisation share documents.

Limits enforced here: an allow-list of file types and a size ceiling. The
size can only be known after the upload (the presigned PUT does not cap
it), so confirm() checks it from S3's own HEAD response and deletes an
oversize object.
"""
from app.documents import services
from app.extensions import db
from app.models.core import Document
from app.utils.errors import APIError

MAX_BYTES = 20 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/csv",
}
DOC_TYPES = {
    "scp": {"insurance", "certificate", "method_statement", "drawing", "invoice", "other"},
    "vnp": {"trade_license", "tax_clearance", "insurance", "certificate", "invoice", "other"},
}


def create_upload(tenant_id, *, owner_type, owner_id, user_id, original_filename, content_type, doc_type):
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise APIError("This file type is not allowed. Use PDF, PNG, JPEG, Word, Excel or CSV.", status=400)
    if doc_type not in DOC_TYPES[owner_type]:
        raise APIError("Unknown document type", status=400)
    document, upload_url = services.create_upload_request(
        tenant_id, original_filename=original_filename, content_type=content_type,
        doc_type=doc_type, requested_by=user_id,
    )
    document.portal_owner_type = owner_type
    document.portal_owner_id = owner_id
    db.session.commit()
    return document, upload_url


def get_owned(tenant_id, *, owner_type, owner_id, document_id) -> Document:
    doc = Document.query.filter_by(
        id=document_id, tenant_id=tenant_id, portal_owner_type=owner_type, portal_owner_id=owner_id
    ).first()
    if not doc:
        raise APIError("Document not found", status=404)
    return doc


def confirm(tenant_id, *, owner_type, owner_id, user_id, document_id) -> Document:
    doc = get_owned(tenant_id, owner_type=owner_type, owner_id=owner_id, document_id=document_id)
    doc = services.confirm_upload(doc, confirmed_by=user_id)
    if doc.size_bytes is not None and doc.size_bytes > MAX_BYTES:
        services.delete_document(doc)
        raise APIError(f"File is larger than the {MAX_BYTES // (1024 * 1024)} MB limit", status=413)
    return doc


def list_owned(tenant_id, *, owner_type, owner_id):
    return (
        Document.query.filter_by(tenant_id=tenant_id, portal_owner_type=owner_type, portal_owner_id=owner_id, status="uploaded")
        .order_by(Document.created_at.desc())
        .all()
    )


def download_url(tenant_id, *, owner_type, owner_id, document_id):
    doc = get_owned(tenant_id, owner_type=owner_type, owner_id=owner_id, document_id=document_id)
    return services.get_download_url(doc)
