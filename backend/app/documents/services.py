"""
Document storage service layer (SRS Section 3.1 / 5.2).

The flow, deliberately not "upload bytes through Flask":

  1. create_upload_request: server creates a Document row (status
     "pending") and hands back a presigned S3 PUT URL. The client
     (browser) uploads the file bytes DIRECTLY to S3 using that URL --
     Flask never sees the file content at all. This is the standard
     production pattern (proxying large file bytes through the app
     server doesn't scale and adds nothing) and is what every module's
     document_id fields have been waiting on since they were built.

  2. confirm_upload: business rule -- a document is only ever marked
     "uploaded" after a REAL HEAD request against S3 confirms the
     object exists, and its size/content-type are read FROM THAT
     RESPONSE, never trusted from whatever the client claims. A client
     that calls confirm without ever actually uploading gets a 409,
     not a silently-accepted lie.

  3. get_download_url: only a document already in "uploaded" status
     can produce a presigned GET URL -- there's nothing real behind a
     "pending" or "failed" document to download.
"""
import uuid

from botocore.exceptions import ClientError

from app.extensions import db, get_s3_client
from app.utils.errors import APIError
from app.models.core import Document


UPLOAD_URL_TTL_SECONDS = 900  # 15 minutes -- long enough for a real upload, short enough to bound exposure
DOWNLOAD_URL_TTL_SECONDS = 300  # 5 minutes -- a download link is meant to be used immediately, not bookmarked


def _bucket(config):
    return config["S3_BUCKET"]


def _build_object_key(tenant_id, original_filename: str) -> str:
    """
    Tenant-prefixed key. RLS on the `documents` table is the actual
    access-control boundary for document METADATA (same as every other
    tenant-scoped table in this platform); this prefix is defense in
    depth at the storage layer itself, and matches how a real S3
    bucket serving many tenants would be organized for operational
    sanity (lifecycle policies, cost allocation, manual audits).
    """
    safe_name = original_filename.replace("/", "_").replace("\\", "_")
    return f"{tenant_id}/{uuid.uuid4()}/{safe_name}"


def create_upload_request(
    tenant_id, *, original_filename, content_type, project_id=None, doc_type=None, requested_by=None
):
    from flask import current_app

    if not original_filename:
        raise APIError("original_filename is required", status=400)

    file_key = _build_object_key(tenant_id, original_filename)

    document = Document(
        tenant_id=tenant_id,
        project_id=project_id,
        file_key=file_key,
        doc_type=doc_type,
        original_filename=original_filename,
        content_type=content_type,
        status="pending",
        uploaded_by=requested_by,
    )
    db.session.add(document)
    db.session.commit()

    s3 = get_s3_client()
    upload_url = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": _bucket(current_app.config),
            "Key": file_key,
            "ContentType": content_type or "application/octet-stream",
        },
        ExpiresIn=UPLOAD_URL_TTL_SECONDS,
    )

    return document, upload_url


def confirm_upload(document: Document, *, confirmed_by=None):
    from flask import current_app

    if document.status == "uploaded":
        raise APIError("Document has already been confirmed as uploaded", status=409)

    s3 = get_s3_client()
    try:
        head = s3.head_object(Bucket=_bucket(current_app.config), Key=document.file_key)
    except ClientError as exc:
        # Business rule: confirming an upload that never actually
        # happened is a real failure, not something to paper over --
        # the object genuinely isn't there.
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code in ("404", "NoSuchKey", "NotFound"):
            document.status = "failed"
            db.session.commit()
            raise APIError(
                "No object was found at the expected storage location -- the upload did not complete",
                status=409,
            )
        raise

    document.status = "uploaded"
    document.size_bytes = head.get("ContentLength")
    # The content type S3 actually stored is authoritative -- it's what
    # a downloading client will actually receive, whatever the
    # original upload request claimed it would be.
    if head.get("ContentType"):
        document.content_type = head["ContentType"]
    document.uploaded_by = confirmed_by or document.uploaded_by
    db.session.commit()
    return document


def get_download_url(document: Document):
    from flask import current_app

    if document.status != "uploaded":
        raise APIError(f"Document is not available for download (status: {document.status})", status=409)

    s3 = get_s3_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": _bucket(current_app.config), "Key": document.file_key},
        ExpiresIn=DOWNLOAD_URL_TTL_SECONDS,
    )


def delete_document(document: Document):
    from flask import current_app

    s3 = get_s3_client()
    try:
        s3.delete_object(Bucket=_bucket(current_app.config), Key=document.file_key)
    except ClientError:
        # Best-effort: if the object was never actually uploaded (a
        # "pending" or "failed" document), there's nothing to delete in
        # S3 at all, and that's fine -- the metadata row deletion below
        # is what actually matters in that case.
        pass

    db.session.delete(document)
    db.session.commit()
