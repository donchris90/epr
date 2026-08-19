"""
The currently-authenticated user's own profile -- "who am I", and
setting a real avatar. Reuses the existing document/S3 infrastructure
(app/documents/) rather than a separate image storage system: an
avatar is just a Document row like any other, with one real,
avatar-specific rule applied on top -- it must actually be an image.
"""
from app.extensions import db
from app.utils.errors import APIError
from app.models.core import User, Document

REAL_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def get_profile(tenant_id, user_id):
    user = User.query.filter_by(id=user_id, tenant_id=tenant_id).first()
    if not user:
        raise APIError("User not found", status=404)
    return user


def set_avatar(tenant_id, user_id, *, document_id):
    """
    Real validation, not trusting the client: only a document already
    in status="uploaded" (confirm_upload has already done a real S3
    HEAD request and verified the object exists) can become an
    avatar, and its content_type -- set from that same real S3
    response, never client-supplied -- must actually be a real image
    type. A client pointing this at someone else's PDF, or at a
    document that was requested but never actually uploaded, is
    rejected honestly, not silently accepted.
    """
    user = User.query.filter_by(id=user_id, tenant_id=tenant_id).first()
    if not user:
        raise APIError("User not found", status=404)

    document = Document.query.filter_by(id=document_id, tenant_id=tenant_id).first()
    if not document:
        raise APIError("Document not found", status=404)
    if document.status != "uploaded":
        raise APIError("This file hasn't finished uploading yet", status=409)
    if document.content_type not in REAL_IMAGE_CONTENT_TYPES:
        raise APIError(
            "Avatar must be a real image", status=400,
            detail=f"Got content type {document.content_type!r}; expected one of {sorted(REAL_IMAGE_CONTENT_TYPES)}.",
        )

    user.avatar_document_id = document.id
    db.session.commit()
    return user


def remove_avatar(tenant_id, user_id):
    user = User.query.filter_by(id=user_id, tenant_id=tenant_id).first()
    if not user:
        raise APIError("User not found", status=404)
    user.avatar_document_id = None
    db.session.commit()
    return user
