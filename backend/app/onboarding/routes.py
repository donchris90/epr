"""
Tenant signup. Base path: /v1/onboarding

This is genuinely public -- unlike almost every other route in this
codebase, there is no tenant context yet when this request arrives, so
it's exempted from the tenant-context middleware's default check the
same way /v1/auth/login is (see app/middleware/tenant_context.py's
PUBLIC_PATHS). Rate limiting (app/__init__.py) applies a stricter
limit here specifically, since an unauthenticated endpoint that
creates real database rows is an abuse target in a way login itself
(which creates nothing) is not.
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, create_refresh_token
from marshmallow import ValidationError

from app.utils.errors import APIError
from app.onboarding import services
from app.onboarding.schemas import SignupSchema
from app.extensions import limiter

bp = Blueprint("onboarding", __name__, url_prefix="/v1/onboarding")


@bp.post("/signup")
@limiter.limit("5 per hour")
def signup():
    try:
        data = SignupSchema().load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))

    result = services.signup_tenant(
        company_name=data["company_name"],
        admin_email=data["admin_email"],
        admin_password=data["admin_password"],
    )

    # Auto-login: the new administrator lands in the app immediately,
    # the same real token shape /v1/auth/login issues -- tenant_id,
    # user_id, role_id, and permissions claims, verified on every
    # subsequent request exactly like any other session. pwd_ts is
    # always None here (see app/auth/jwt_utils.py:build_auth_claims's
    # own docstring) -- a brand-new user has never changed their
    # password.
    claims = {
        "tenant_id": str(result["tenant_id"]),
        "user_id": str(result["user_id"]),
        "role_id": str(result["admin_role_id"]),
        "permissions": result["admin_permissions"],
        "pwd_ts": None,
    }
    access_token = create_access_token(identity=str(result["user_id"]), additional_claims=claims)
    refresh_token = create_refresh_token(identity=str(result["user_id"]), additional_claims=claims)

    return jsonify({"tenant_id": str(result["tenant_id"]), "access_token": access_token, "refresh_token": refresh_token}), 201
