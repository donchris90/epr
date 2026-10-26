"""
Self-service forgot-password / reset-password for the Subcontractor
Portal (SCP), Vendor Portal (VNP) and Client Portal (CLP) -- previously genuinely missing
(see docs/SUBCONTRACTOR_VENDOR_PORTAL_GAPS.md): a portal user who lost
their password could only be helped by staff re-creating the account.

Mirrors the staff flow in app/auth/services.py deliberately:
  - tokens are stored as SHA-256 hashes in a table OUTSIDE RLS (the
    requester has no tenant context yet), single-use, 1 hour expiry;
  - request_portal_password_reset never raises and never reveals
    whether an account exists (account-enumeration protection);
  - a successful reset sets `password_changed_at`, which is embedded
    in portal tokens as `pwd_ts` and checked on refresh and on every
    request, so all earlier sessions stop working immediately.

One table serves both portals; `portal_type` ("scp" | "vnp" | "clp") says
which user table `portal_user_id` refers to (no FK for that reason).
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID

from app.auth.jwt_utils import hash_password
from app.extensions import db
from app.models.base import UUIDPrimaryKeyMixin
from app.utils.errors import APIError

RESET_TOKEN_TTL_HOURS = 1
INVALID_LINK = "This password reset link is invalid or has expired"


class PortalPasswordResetToken(db.Model, UUIDPrimaryKeyMixin):
    """Deliberately NOT tenant-scoped / NOT RLS-protected, for the same
    reason as PasswordResetToken: the token must be resolvable before
    any tenant context exists. Only the SHA-256 hash is stored."""

    __tablename__ = "portal_password_reset_tokens"

    portal_type = db.Column(db.String(8), nullable=False)
    tenant_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tenants.id"), nullable=False)
    portal_user_id = db.Column(UUID(as_uuid=True), nullable=False)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())


def _portal_config(portal_type):
    """Resolved lazily to avoid import cycles with the module models."""
    if portal_type == "scp":
        from app.modules.scp.models import SubcontractorPortalUser, SubcontractorPortalEmailIndex

        return {
            "user": SubcontractorPortalUser,
            "index": SubcontractorPortalEmailIndex,
            "index_fk": "portal_user_id",
            "path": "/subcontractor/reset-password",
            "label": "Subcontractor Portal",
        }
    if portal_type == "vnp":
        from app.modules.vnp.models import VendorPortalUser, VendorPortalEmailIndex

        return {
            "user": VendorPortalUser,
            "index": VendorPortalEmailIndex,
            "index_fk": "vendor_user_id",
            "path": "/vendor/reset-password",
            "label": "Vendor Portal",
        }
    if portal_type == "clp":
        from app.modules.clp.models import ClientPortalUser, ClientPortalEmailIndex

        return {
            "user": ClientPortalUser,
            "index": ClientPortalEmailIndex,
            "index_fk": "client_user_id",
            "path": "/portal/reset-password",
            "label": "Client Portal",
        }
    raise ValueError(f"Unknown portal type {portal_type!r}")


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def request_portal_password_reset(portal_type: str, email: str) -> None:
    """Silent by design -- see module docstring. One email per tenant
    the address is registered with (a subcontractor/vendor can work
    with several contractors), each with its own token."""
    if not email:
        return
    cfg = _portal_config(portal_type)
    index_rows = cfg["index"].query.filter_by(email=email).all()
    if not index_rows:
        return

    raw_tokens = []
    for index_row in index_rows:
        with db.session.begin_nested():
            db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(index_row.tenant_id)})
            user = db.session.get(cfg["user"], getattr(index_row, cfg["index_fk"]))
            if not user or not user.is_active:
                continue
            raw = secrets.token_urlsafe(32)
            db.session.add(
                PortalPasswordResetToken(
                    portal_type=portal_type,
                    tenant_id=index_row.tenant_id,
                    portal_user_id=user.id,
                    token_hash=_hash_token(raw),
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=RESET_TOKEN_TTL_HOURS),
                )
            )
            raw_tokens.append(raw)

    db.session.commit()

    # Fire-and-forget exactly like the staff flow: a failed/slow email
    # must never surface to the caller.
    try:
        from flask import current_app
        from app.notifications.tasks import send_email_notification

        for raw in raw_tokens:
            reset_url = f"{current_app.config['FRONTEND_URL']}{cfg['path']}?token={raw}"
            send_email_notification.delay(
                to_address=email,
                subject=f"Reset your SiteForge {cfg['label']} password",
                body=(
                    f"A password reset was requested for your SiteForge {cfg['label']} account.\n\n"
                    f"Reset your password: {reset_url}\n\n"
                    f"This link expires in {RESET_TOKEN_TTL_HOURS} hour(s). "
                    "If you didn't request this, you can safely ignore this email."
                ),
            )
    except Exception:
        logging.getLogger(__name__).warning(
            "Portal reset token created but the email failed to send/queue for %s", email, exc_info=True
        )


def reset_portal_password(portal_type: str, raw_token: str, new_password: str) -> None:
    if len(new_password) < 8:
        raise APIError("Password must be at least 8 characters", status=400)

    cfg = _portal_config(portal_type)
    row = PortalPasswordResetToken.query.filter_by(token_hash=_hash_token(raw_token), portal_type=portal_type).first()
    now = datetime.now(timezone.utc)
    if not row or row.used_at is not None or row.expires_at < now:
        raise APIError(INVALID_LINK, status=400)

    with db.session.begin_nested():
        db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(row.tenant_id)})
        user = db.session.get(cfg["user"], row.portal_user_id)
        if not user or not user.is_active:
            raise APIError(INVALID_LINK, status=400)
        user.password_hash = hash_password(new_password)
        user.password_changed_at = now
        row.used_at = now

    db.session.commit()


def check_portal_pwd_ts(portal_type, tenant_id, user_id, claim_pwd_ts) -> bool:
    """True while the token's pwd_ts still matches the user's current
    password_changed_at. A user that can't be found passes (same
    narrow-job reasoning as jwt_utils.check_pwd_ts_claim)."""
    cfg = _portal_config(portal_type)
    with db.session.begin_nested():
        db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})
        user = db.session.get(cfg["user"], user_id)
    if not user:
        return True
    current = user.password_changed_at.isoformat() if user.password_changed_at else None
    return current == claim_pwd_ts
