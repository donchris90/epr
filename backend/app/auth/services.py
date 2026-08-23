"""
The currently-authenticated user's own profile -- "who am I", and
setting a real avatar. Reuses the existing document/S3 infrastructure
(app/documents/) rather than a separate image storage system -- an
avatar is just a Document row like any other, with one real,
avatar-specific rule applied on top -- it must actually be an image.

Also: real staff password reset/change -- previously genuinely missing
entirely (no forgot-password, reset-password, or change-password
endpoint existed anywhere in this backend before this).
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.utils.errors import APIError
from app.models.core import User, Document, EmailTenantIndex, PasswordResetToken
from app.auth.jwt_utils import hash_password, verify_password

RESET_TOKEN_TTL_HOURS = 1

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


def _hash_reset_token(raw_token: str) -> str:
    """SHA-256, not Argon2 -- same reasoning as Invitation.token_hash's
    own established pattern (app/org/services.py): a reset token needs
    to be looked up directly by its hash, which Argon2's per-hash
    random salt makes impossible. A plain SHA-256 digest of a 32-byte
    cryptographically random token is still secure for this."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def request_password_reset(email: str) -> None:
    """
    Real, deliberately silent -- never raises, never returns anything
    that would let a caller distinguish "email exists, reset email
    sent" from "no account with that email" (the real requirement:
    a forgot-password endpoint that reveals whether an account exists
    is a real, well-known account-enumeration vulnerability). The
    route built on top of this always returns the same 200 regardless
    of what happens inside here.

    Same real, established cross-tenant lookup pattern as login itself
    (app/auth/jwt_utils.py:authenticate_user) -- EmailTenantIndex
    resolves the tenant before any RLS-scoped query can run at all.
    """
    if not email:
        return

    index_row = EmailTenantIndex.query.filter_by(email=email).first()
    if not index_row:
        return

    from sqlalchemy import text

    with db.session.begin_nested():
        db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(index_row.tenant_id)})
        user = db.session.get(User, index_row.user_id)

        if not user or user.status != "active":
            return

        raw_token = secrets.token_urlsafe(32)
        token = PasswordResetToken(
            tenant_id=index_row.tenant_id,
            user_id=user.id,
            token_hash=_hash_reset_token(raw_token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=RESET_TOKEN_TTL_HOURS),
        )
        db.session.add(token)

    db.session.commit()

    # Real notification, fire-and-forget the same real way every other
    # notification in this codebase is (app/notifications/tasks.py) --
    # a failed/slow email send must never surface back to this
    # function's caller or block the request; see
    # app/org/services.py:_send_invitation_email's own docstring on
    # the real production bug (a synchronous eager-mode crash) this
    # exact try/except pattern was fixed for.
    try:
        from flask import current_app
        from app.notifications.tasks import send_email_notification

        reset_url = f"{current_app.config['FRONTEND_URL']}/reset-password?token={raw_token}"
        send_email_notification.delay(
            to_address=email,
            subject="Reset your SiteForge password",
            body=(
                "A password reset was requested for your SiteForge account.\n\n"
                f"Reset your password: {reset_url}\n\n"
                f"This link expires in {RESET_TOKEN_TTL_HOURS} hour(s). "
                "If you didn't request this, you can safely ignore this email."
            ),
        )
    except Exception:
        import logging

        logging.getLogger(__name__).warning("Password reset token created but the notification email failed to send/queue for %s", email, exc_info=True)


def reset_password(raw_token: str, new_password: str) -> None:
    """
    Real, single-use, expiring token validation -- same two-step
    cross-tenant lookup as get_invitation_by_token
    (app/org/services.py), applied to password reset tokens instead.
    Setting password_changed_at is the real point: this is what
    actually invalidates every previously-issued session for this
    user immediately (see app/auth/jwt_utils.py:build_auth_claims and
    check_pwd_ts_claim), matching this task's own explicit
    requirement to revoke existing sessions after a successful reset.
    """
    if len(new_password) < 8:
        raise APIError("Password must be at least 8 characters", status=400)

    token_hash = _hash_reset_token(raw_token)
    index_row = PasswordResetToken.query.filter_by(token_hash=token_hash).first()
    if not index_row:
        raise APIError("This password reset link is invalid or has expired", status=400)

    now = datetime.now(timezone.utc)
    if index_row.used_at is not None or index_row.expires_at < now:
        raise APIError("This password reset link is invalid or has expired", status=400)

    from sqlalchemy import text

    with db.session.begin_nested():
        db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(index_row.tenant_id)})
        user = db.session.get(User, index_row.user_id)
        if not user:
            raise APIError("This password reset link is invalid or has expired", status=400)

        user.password_hash = hash_password(new_password)
        user.password_changed_at = now
        index_row.used_at = now

    db.session.commit()


def change_password(tenant_id, user_id, *, current_password: str, new_password: str) -> None:
    """Real, requires the actual current password (not just an active
    session) before allowing a change -- a stolen, still-logged-in
    session alone shouldn't be enough to lock the real owner out by
    changing their password. Also sets password_changed_at, invalidating
    every OTHER session immediately -- including, deliberately, the
    one making this exact request; the frontend re-authenticates with
    the new password rather than assuming this session stays valid."""
    if len(new_password) < 8:
        raise APIError("New password must be at least 8 characters", status=400)

    user = User.query.filter_by(id=user_id, tenant_id=tenant_id).first()
    if not user:
        raise APIError("User not found", status=404)

    if not verify_password(user.password_hash, current_password):
        raise APIError("Current password is incorrect", status=400)

    user.password_hash = hash_password(new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    db.session.commit()
