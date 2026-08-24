"""
Organization user management. Base path: /v1/org

Reading membership (org:read) is broader than managing it
(org:manage), matching the same pattern used across this codebase.
The two accept-invitation endpoints take no auth at all by design --
an invitee isn't logged in yet -- and are listed in
app/middleware/tenant_context.py's PUBLIC_PATHS as fixed paths (the
token travels in the request body/query, not the URL path, so these
stay exact-match entries rather than needing prefix-based public-path
matching).
"""
from flask import Blueprint, g, jsonify, request
from flask_jwt_extended import create_access_token, create_refresh_token

from app.org import services
from app.org.schemas import (
    CompanySchema,
    UserSchema, InvitationSchema, CreateInvitationSchema, AcceptInvitationSchema, ChangeRoleSchema,
    RoleSchema, CreateRoleSchema, UpdateRoleSchema,
)
from app.org.permissions_catalog import get_permission_catalog
from app.utils.decorators import require_permission
from app.utils.errors import APIError

bp = Blueprint("org", __name__, url_prefix="/v1/org")

user_schema = UserSchema()
invitation_schema = InvitationSchema()
role_schema = RoleSchema()
company_schema = CompanySchema()


def _load(schema):
    data = request.get_json(force=True) or {}
    errors = schema.validate(data)
    if errors:
        raise APIError("Validation failed", status=400, detail=str(errors))
    return schema.load(data)


@bp.get("/members")
@require_permission("org:read")
def list_members():
    result = services.list_org_members(g.tenant_id)
    return jsonify({
        "users": user_schema.dump(result["users"], many=True),
        "pending_invitations": invitation_schema.dump(result["pending_invitations"], many=True),
    })


@bp.get("/companies")
@require_permission("org:read")
def list_companies():
    """Real, previously genuinely missing -- app.models.core.Company
    (this endpoint) is the actual foreign-key target of
    Project.company_id, and had no list/create endpoint anywhere in
    this backend before this fix. The project-creation form's own
    Company dropdown was fetching from GET /v1/fin/companies instead
    -- a real, but entirely different table (fin_companies, FIN-12's
    own multi-entity accounting concept) -- so every real project
    creation failed with an unhandled foreign-key violation
    regardless of what was selected."""
    companies = services.list_companies(g.tenant_id)
    return jsonify({"data": company_schema.dump(companies, many=True)})


@bp.post("/companies")
@require_permission("org:manage")
def create_company():
    data = _load(CompanySchema())
    company = services.create_company(g.tenant_id, **data)
    return jsonify(company_schema.dump(company)), 201


@bp.get("/roles")
@require_permission("org:read")
def list_roles():
    roles = services.list_roles(g.tenant_id)
    return jsonify({"data": role_schema.dump(roles, many=True)})


@bp.get("/permissions-catalog")
@require_permission("org:read")
def permissions_catalog():
    """Real, grouped, friendly-labeled list of every permission that
    can actually be granted -- see app/org/permissions_catalog.py's
    own docstring for why this is hand-maintained rather than scanned
    from route decorators at runtime."""
    return jsonify({"data": get_permission_catalog()})


@bp.post("/roles")
@require_permission("org:manage")
def create_role():
    data = _load(CreateRoleSchema())
    role = services.create_role(
        g.tenant_id, name=data["name"], permission_set=data["permission_set"], caller_permissions=g.permissions,
    )
    return jsonify(role_schema.dump(role)), 201


@bp.put("/roles/<uuid:role_id>")
@require_permission("org:manage")
def update_role(role_id):
    data = _load(UpdateRoleSchema())
    role = services.update_role(
        g.tenant_id, role_id, name=data.get("name"), permission_set=data.get("permission_set"), caller_permissions=g.permissions,
    )
    return jsonify(role_schema.dump(role))


@bp.delete("/roles/<uuid:role_id>")
@require_permission("org:manage")
def delete_role(role_id):
    services.delete_role(g.tenant_id, role_id)
    return "", 204


@bp.get("/seats")
@require_permission("org:read")
def get_seats():
    limit = services.get_seat_limit(g.tenant_id)
    used = services.count_seats_in_use(g.tenant_id)
    return jsonify({
        "seat_limit": limit,
        "seats_used": used,
        "seats_remaining": None if limit is None else max(0, limit - used),
    })


@bp.post("/invitations")
@require_permission("org:manage")
def create_invitation():
    data = _load(CreateInvitationSchema())
    invitation = services.create_invitation(
        g.tenant_id, email=data["email"], role_id=data["role_id"], invited_by_user_id=g.user_id,
        department=data.get("department"), job_title=data.get("job_title"), message=data.get("message"),
    )
    return jsonify(invitation_schema.dump(invitation)), 201


@bp.post("/invitations/<uuid:invitation_id>/resend")
@require_permission("org:manage")
def resend_invitation(invitation_id):
    invitation = services.resend_invitation(g.tenant_id, invitation_id)
    return jsonify(invitation_schema.dump(invitation))


@bp.post("/invitations/<uuid:invitation_id>/cancel")
@require_permission("org:manage")
def cancel_invitation(invitation_id):
    invitation = services.cancel_invitation(g.tenant_id, invitation_id)
    return jsonify(invitation_schema.dump(invitation))


@bp.post("/users/<uuid:user_id>/suspend")
@require_permission("org:manage")
def suspend_user(user_id):
    user = services.suspend_user(g.tenant_id, user_id)
    return jsonify(user_schema.dump(user))


@bp.post("/users/<uuid:user_id>/reactivate")
@require_permission("org:manage")
def reactivate_user(user_id):
    user = services.reactivate_user(g.tenant_id, user_id)
    return jsonify(user_schema.dump(user))


@bp.post("/users/<uuid:user_id>/remove")
@require_permission("org:manage")
def remove_user(user_id):
    user = services.remove_user(g.tenant_id, user_id)
    return jsonify(user_schema.dump(user))


@bp.post("/users/<uuid:user_id>/role")
@require_permission("org:manage")
def change_role(user_id):
    data = _load(ChangeRoleSchema())
    user = services.change_user_role(g.tenant_id, user_id, data["role_id"])
    return jsonify(user_schema.dump(user))


# --- Public accept-invitation flow (no auth, no tenant context) --------------

@bp.get("/invitations/preview")
def preview_invitation():
    """Real, honest preview -- org name, inviter's email, assigned
    role -- shown before the invitee sets a password, matching Phase
    32's "see organization name, see inviter" requirement."""
    token = request.args.get("token", "")
    invitation = services.get_invitation_by_token(token)
    if not invitation:
        raise APIError("This invitation is invalid or has expired", status=400)

    from app.models.core import Tenant, User

    tenant = Tenant.query.filter_by(id=invitation.tenant_id).first()
    inviter = User.query.filter_by(id=invitation.invited_by_user_id).first() if invitation.invited_by_user_id else None

    return jsonify({
        "organization_name": tenant.name if tenant else None,
        "invited_by_email": inviter.email if inviter else None,
        "email": invitation.email,
        "role_name": invitation.role.name if invitation.role else None,
    })


@bp.post("/invitations/accept")
def accept_invitation():
    """Real account creation, immediately logged in -- returns the
    same real access/refresh token pair app/auth/routes.py's ordinary
    login issues, so the new user lands straight in the app rather
    than being asked to log in again with the password they just set."""
    data = _load(AcceptInvitationSchema())
    result = services.accept_invitation(data["token"], password=data["password"])

    claims = {
        "tenant_id": result["tenant_id"], "user_id": result["user_id"],
        "role_id": result["role_id"], "permissions": result["permissions"],
        # None -- a brand-new user (see app/auth/jwt_utils.py:build_auth_claims's
        # own docstring) has never changed their password.
        "pwd_ts": None,
    }
    access_token = create_access_token(identity=result["user_id"], additional_claims=claims)
    refresh_token = create_refresh_token(identity=result["user_id"], additional_claims=claims)
    return jsonify({"access_token": access_token, "refresh_token": refresh_token}), 201
