"""
Authentication endpoints (SRS Section 6.2).

    POST /v1/auth/login    email/password (or SSO token) -> access + refresh token
    POST /v1/auth/refresh  refresh token -> new access token
    POST /v1/auth/logout   revokes the refresh token

Access tokens are JWTs carrying tenant_id, user_id, role_id, and
permissions claims, verified on every request (see middleware/tenant_context.py)
and used to set the RLS session variable.

Client Portal users do NOT authenticate through this endpoint family --
that claim in an earlier revision of this docstring was aspirational,
not actual: `authenticate_user` below only ever looks up the internal
`users` table, and `ClientPortalUser` had no password of any kind until
the client portal build added one. A real client-facing login now
exists at POST /v1/clp/auth/login (app/modules/clp/routes.py),
deliberately a SEPARATE endpoint family issuing tokens with their own
`is_client: true` claim -- see that module's docstring for why a
shared family was rejected. Vendor Portal (VNP) has the identical gap
STILL OPEN (see docs/CLIENT_PORTAL_GAPS.md); nothing below authenticates
a VNP user either.
"""
from flask import Blueprint, g, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
)

from app.auth.jwt_utils import authenticate_user, revoke_refresh_token, build_auth_claims, check_pwd_ts_claim
from app.extensions import limiter, db

bp = Blueprint("auth", __name__, url_prefix="/v1/auth")


@bp.post("/login")
@limiter.limit("10 per minute")
def login():
    data = request.get_json(force=True) or {}
    email = data.get("email")
    password = data.get("password")

    user = authenticate_user(email, password)
    if not user:
        return jsonify({"type": "about:blank", "title": "Invalid credentials", "status": 401}), 401

    claims = build_auth_claims(user)

    # Committed here, deliberately -- after claims are already built
    # from `user`'s attributes (a commit expires every object in the
    # session, confirmed via a real reproduction that reading
    # user.password_changed_at any earlier broke this).
    db.session.commit()

    # claims["user_id"], not user.id -- confirmed via a second real
    # reproduction that re-reading user.id here (after the commit
    # above already expired it) triggered a refresh query with no
    # tenant context left. The value was already safely captured in
    # claims before the commit; no reason to read it from the
    # (now-expired) ORM object a second time.
    access_token = create_access_token(identity=claims["user_id"], additional_claims=claims)
    refresh_token = create_refresh_token(identity=claims["user_id"], additional_claims=claims)

    return jsonify({"access_token": access_token, "refresh_token": refresh_token})


@bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    import time

    identity = get_jwt_identity()
    old_claims = get_jwt()

    # Client portal build: a client-issued refresh token (see
    # app/modules/clp/routes.py:client_refresh) must never be
    # refreshable here -- this route has no idea how to re-derive
    # clp:read/clp:write permissions or the is_client claim, and
    # silently dropping is_client on refresh would have quietly
    # disabled the client-can-only-act-as-itself check in
    # app/modules/clp/routes.py:_get_client_user_or_404 for the
    # resulting token.
    if old_claims.get("is_client"):
        return jsonify({"type": "about:blank", "title": "Not a staff session", "status": 401}), 401

    # Real bug found and fixed while building password reset, not
    # cosmetic: this route is exempt from the tenant-context
    # middleware's own pwd_ts check entirely (it takes a refresh
    # token, not an access token, which that middleware doesn't
    # handle) -- previously this just carried over the OLD token's
    # claims blindly, with no database check of any kind. An old
    # refresh token could keep minting fresh access tokens forever
    # after a password change, completely defeating the whole point
    # of pwd_ts-based session invalidation. Explicitly re-checked
    # here, and claims rebuilt fresh from the real, current user/role
    # state rather than trusted from the token being refreshed.
    tenant_id = old_claims.get("tenant_id")
    user_id = old_claims.get("user_id")
    if not check_pwd_ts_claim(tenant_id, user_id, old_claims.get("pwd_ts")):
        return jsonify({"type": "about:blank", "title": "Session no longer valid", "status": 401}), 401

    from app.models.core import User
    from sqlalchemy import text

    with db.session.begin_nested():
        db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})
        user = db.session.get(User, user_id)
    if not user:
        return jsonify({"type": "about:blank", "title": "Session no longer valid", "status": 401}), 401

    new_claims = build_auth_claims(user)

    access_token = create_access_token(identity=identity, additional_claims=new_claims)

    # Rotation: the refresh token just used is revoked immediately, and
    # a new one issued in its place -- a refresh token is single-use.
    # This bounds the damage a leaked refresh token can do (one use,
    # not up to 30 days of silent reuse) and lets a stolen-and-reused
    # token be detected: if BOTH the legitimate client and an attacker
    # try to use the same already-rotated token, the second one to
    # arrive gets a 401, which is a visible signal something is wrong.
    old_jti = old_claims["jti"]
    remaining_seconds = max(int(old_claims["exp"] - time.time()), 1)
    revoke_refresh_token(old_jti, expires_in_seconds=remaining_seconds)

    refresh_token = create_refresh_token(identity=identity, additional_claims=new_claims)

    return jsonify({"access_token": access_token, "refresh_token": refresh_token})


@bp.post("/logout")
@jwt_required(refresh=True)
def logout():
    import time

    claims = get_jwt()
    jti = claims["jti"]
    remaining_seconds = max(int(claims["exp"] - time.time()), 1)
    revoke_refresh_token(jti, expires_in_seconds=remaining_seconds)
    return jsonify({"status": "logged_out"})


def _profile_response(user):
    """Real, ready-to-use avatar URL, not just a raw document_id --
    reuses the existing document download-URL logic
    (app/documents/services.py) so the frontend can display the image
    directly without a separate round-trip."""
    from app.documents.services import get_download_url
    from app.models.core import Document

    avatar_url = None
    if user.avatar_document_id:
        document = Document.query.filter_by(id=user.avatar_document_id).first()
        if document and document.status == "uploaded":
            avatar_url = get_download_url(document)

    return {
        "id": str(user.id),
        "email": user.email,
        "status": user.status,
        "department": user.department,
        "job_title": user.job_title,
        "avatar_url": avatar_url,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


@bp.get("/me")
@jwt_required()
def get_me():
    from app.auth.services import get_profile

    user = get_profile(g.tenant_id, g.user_id)
    return jsonify(_profile_response(user))


@bp.put("/me/avatar")
@jwt_required()
def set_my_avatar():
    from app.auth.services import set_avatar

    data = request.get_json(force=True) or {}
    document_id = data.get("document_id")
    if not document_id:
        from app.utils.errors import APIError

        raise APIError("document_id is required", status=400)

    user = set_avatar(g.tenant_id, g.user_id, document_id=document_id)
    return jsonify(_profile_response(user))


@bp.delete("/me/avatar")
@jwt_required()
def delete_my_avatar():
    from app.auth.services import remove_avatar

    user = remove_avatar(g.tenant_id, g.user_id)
    return jsonify(_profile_response(user))


@bp.post("/forgot-password")
@limiter.limit("5 per hour")
def forgot_password():
    """
    Real, previously genuinely missing endpoint. Deliberately always
    returns the same 200 regardless of whether the email matches a
    real account -- app/auth/services.py:request_password_reset's own
    docstring on why revealing that is a real account-enumeration
    vulnerability, not a hypothetical one.
    """
    from marshmallow import ValidationError

    from app.auth.schemas import ForgotPasswordSchema
    from app.auth.services import request_password_reset
    from app.utils.errors import APIError

    try:
        data = ForgotPasswordSchema().load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))

    request_password_reset(data["email"])
    return jsonify({"message": "If an account exists for that email, a reset link has been sent."})


@bp.post("/reset-password")
@limiter.limit("10 per hour")
def reset_password_route():
    from marshmallow import ValidationError

    from app.auth.schemas import ResetPasswordSchema
    from app.auth.services import reset_password
    from app.utils.errors import APIError

    try:
        data = ResetPasswordSchema().load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))

    reset_password(data["token"], data["new_password"])
    return jsonify({"message": "Password reset successfully."})


@bp.put("/me/password")
@jwt_required()
def change_my_password():
    from marshmallow import ValidationError

    from app.auth.schemas import ChangePasswordSchema
    from app.auth.services import change_password
    from app.utils.errors import APIError

    try:
        data = ChangePasswordSchema().load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))

    change_password(g.tenant_id, g.user_id, current_password=data["current_password"], new_password=data["new_password"])
    return jsonify({"message": "Password changed successfully."})
