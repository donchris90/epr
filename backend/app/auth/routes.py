"""
Authentication endpoints (SRS Section 6.2).

    POST /v1/auth/login    email/password (or SSO token) -> access + refresh token
    POST /v1/auth/refresh  refresh token -> new access token
    POST /v1/auth/logout   revokes the refresh token

Access tokens are JWTs carrying tenant_id, user_id, role_id, and
permissions claims, verified on every request (see middleware/tenant_context.py)
and used to set the RLS session variable.

External portal users (Client Portal, Vendor Portal) authenticate through
this same endpoint family but receive tokens scoped to a restricted
permission set (SRS Section 8).
"""
from flask import Blueprint, g, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
)

from app.auth.jwt_utils import authenticate_user, revoke_refresh_token
from app.extensions import limiter

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

    from app.models.core import Role

    role_permissions = []
    if user.role_id:
        role = Role.query.get(user.role_id)
        if role:
            role_permissions = role.permission_set or []

    claims = {
        "tenant_id": str(user.tenant_id),
        "user_id": str(user.id),
        "role_id": str(user.role_id) if user.role_id else None,
        "permissions": role_permissions,
    }

    access_token = create_access_token(identity=str(user.id), additional_claims=claims)
    refresh_token = create_refresh_token(identity=str(user.id), additional_claims=claims)

    return jsonify({"access_token": access_token, "refresh_token": refresh_token})


@bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    import time

    identity = get_jwt_identity()
    old_claims = get_jwt()
    new_claims = {
        "tenant_id": old_claims.get("tenant_id"),
        "user_id": old_claims.get("user_id"),
        "role_id": old_claims.get("role_id"),
        "permissions": old_claims.get("permissions", []),
    }

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
