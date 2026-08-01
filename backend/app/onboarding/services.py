"""
Tenant self-service signup (SRS Section 3.1 -- new tenant provisioning).

Before this existed, every tenant used anywhere in this build was
pre-seeded directly in the database by a test fixture or a manual
script -- there was no path for a real company to actually sign up.

The transaction sequence deliberately mirrors the pattern used
throughout every module in this codebase for tenant-scoped writes
outside a request context: create the Tenant row (which has no RLS at
all -- it's the root of the tenant hierarchy, not scoped to one), then
`SET LOCAL app.tenant_id` to the newly-created tenant's own id before
inserting the Role and User rows, which DO have RLS. Committing the
whole thing atomically means a failure partway through (e.g. a
duplicate-email race) leaves no orphaned tenant behind.
"""
import re

from sqlalchemy import text

from app.extensions import db
from app.utils.errors import APIError
from app.auth.jwt_utils import hash_password
from app.models.core import Tenant, Role, User, EmailTenantIndex


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8

# A new tenant's first user is its administrator, with the same
# unrestricted-within-tenant permission shape ("*") used by every
# `permissions: ["*"]` claim already exercised throughout this
# codebase's own tests -- RLS still confines every query to this one
# tenant regardless, so "*" here means "full access within this
# tenant," not "full access to the platform."
DEFAULT_ADMIN_PERMISSIONS = ["*"]


def _validate_signup_input(*, company_name, admin_email, admin_password):
    if not company_name or not company_name.strip():
        raise APIError("company_name is required", status=400)
    if not admin_email or not EMAIL_RE.match(admin_email):
        raise APIError("A valid admin_email is required", status=400)
    if not admin_password or len(admin_password) < MIN_PASSWORD_LENGTH:
        raise APIError(f"admin_password must be at least {MIN_PASSWORD_LENGTH} characters", status=400)


def signup_tenant(*, company_name, admin_email, admin_password):
    """
    Note: there's deliberately no admin_name parameter here -- the
    User model (app/models/core.py) has no name field to put one in.
    Accepting a name and silently discarding it would be worse than
    not accepting it at all.
    """
    _validate_signup_input(company_name=company_name, admin_email=admin_email, admin_password=admin_password)

    tenant = Tenant(name=company_name.strip())
    db.session.add(tenant)
    db.session.flush()  # assigns tenant.id without ending the transaction

    # Every subsequent write in this same transaction touches
    # RLS-protected tables, so the GUC has to be set before them --
    # exactly the same requirement (and the same reason) as every
    # other tenant-scoped write made outside a real HTTP request
    # elsewhere in this codebase (see tests/conftest.py's _as_tenant,
    # or app/documents/services.py's own test suite).
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant.id)})

    admin_role = Role(tenant_id=tenant.id, name="Administrator", permission_set=DEFAULT_ADMIN_PERMISSIONS)
    db.session.add(admin_role)
    db.session.flush()

    user = User(
        tenant_id=tenant.id,
        email=admin_email.strip().lower(),
        password_hash=hash_password(admin_password),
        role_id=admin_role.id,
        status="active",
    )
    db.session.add(user)
    db.session.flush()

    # Not RLS-protected (see app/models/core.py:EmailTenantIndex), so
    # this insert doesn't depend on the SET LOCAL above at all -- but
    # it's still part of the same atomic transaction, so a failure
    # here rolls back the whole signup rather than leaving a user who
    # exists but can never be found at login.
    db.session.add(EmailTenantIndex(email=user.email, user_id=user.id, tenant_id=tenant.id))
    db.session.flush()

    # Captured as plain values BEFORE commit, deliberately -- Flask-
    # SQLAlchemy's default expire_on_commit=True means every attribute
    # on these ORM objects would trigger a fresh SELECT the first time
    # it's touched after commit() below, and that SELECT would run in
    # a brand new transaction with no app.tenant_id GUC set at all
    # (the SET LOCAL above only lasted for the transaction that's
    # about to end). Returning primitives sidesteps the whole problem
    # rather than requiring the caller to know about it.
    result = {
        "tenant_id": tenant.id,
        "admin_role_id": admin_role.id,
        "admin_permissions": list(admin_role.permission_set),
        "user_id": user.id,
    }

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise APIError("Could not complete signup -- please try again", status=500)

    return result
