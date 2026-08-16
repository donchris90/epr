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
