"""
Shared route decorators — RBAC permission enforcement (SRS Section 8).
"""
from functools import wraps

from flask import g

from app.utils.errors import APIError


def require_permission(permission: str):
    """
    Usage:
        @bp.post("/purchase-orders")
        @require_permission("procurement:create")
        def create_po(): ...

    Checked in addition to (never instead of) tenant-scope Row-Level
    Security, per the three-layer access model in SRS Section 8.1.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            permissions = getattr(g, "permissions", [])
            if permission not in permissions and "*" not in permissions:
                raise APIError("Forbidden", status=403, detail=f"Missing permission: {permission}")
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def require_platform_admin(fn):
    """
    A platform admin token carries no tenant_id and no tenant-scoped
    permissions claim at all (see app/platform_admin/routes.py's
    login), so require_permission above can never apply to it --
    checks the real, distinct `is_platform_admin` JWT claim directly
    instead. See app/platform_admin/models.py's module docstring for
    why this is a wholly separate account type, not a powerful
    permission on an ordinary tenant user.
    """
    from flask_jwt_extended import get_jwt

    @wraps(fn)
    def wrapper(*args, **kwargs):
        claims = get_jwt() or {}
        if not claims.get("is_platform_admin"):
            raise APIError("Forbidden", status=403, detail="Platform admin access required")
        return fn(*args, **kwargs)

    return wrapper
