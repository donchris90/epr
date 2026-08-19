"""
Authentication helpers: password verification and refresh-token revocation.
Passwords are hashed with Argon2id (SRS Section 10.4) -- no plaintext or
reversibly-encrypted password storage.

Real bug found from a live 502 error on the invitation-accept flow, not
by inspection: argon2-cffi's PasswordHasher() with no arguments uses
its own library default -- 64 MiB memory cost, 4-way parallelism, per
single hash operation. That's a reasonable choice on a well-resourced
server, but on Render's free tier (512 MB total RAM, shared across
multiple gunicorn worker processes -- 4 were observed booting in this
deployment's own logs) a single password hash genuinely competing for
that much memory is a real, plausible cause of an out-of-memory kill
mid-request, which is exactly what a 502 with no application-level
error response at all looks like from the outside -- the worker
process dies before Flask ever gets to return anything, so there's no
clean error for CORS headers to even attach to.

Explicitly configured to OWASP's own current documented minimum
(Password Storage Cheat Sheet, 2026): m=19 MiB, t=2, p=1 -- a real,
legitimate, still-secure standard specifically recommended for
resource-constrained environments, confirmed directly against
multiple current sources before making this change, not guessed at or
weakened below any accepted practice.
"""
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import text

from app.extensions import db
from app.models.core import User, EmailTenantIndex, Tenant

_hasher = PasswordHasher(memory_cost=19456, time_cost=2, parallelism=1)


def hash_password(plain_password: str) -> str:
    return _hasher.hash(plain_password)


def verify_password(password_hash: str, plain_password: str) -> bool:
    """Public counterpart to hash_password -- lets other real account
    types outside app.models.core.User (e.g. app/platform_admin/) verify
    a password without reaching into this module's own PasswordHasher
    instance directly."""
    try:
        _hasher.verify(password_hash, plain_password)
        return True
    except VerifyMismatchError:
        return False


def authenticate_user(email: str, password: str):
    """
    Two-step lookup, deliberately:

    1. Find the user's tenant_id by email via EmailTenantIndex -- a
       small table deliberately outside RLS entirely (see
       app/models/core.py:EmailTenantIndex), queried through the
       normal db.session like anything else. This used to require a
       separate BYPASSRLS database role and its own connection
       (app/extensions.py:get_auth_engine) -- replaced after that
       role turned out to be impossible to provision from application
       code on a real managed Postgres deployment (Postgres requires
       the granting role to itself have BYPASSRLS to hand it to
       anyone else, which the hosting provider's own database role
       didn't have).
    2. Once the tenant is known, fetch the row through the normal
       tenant-scoped `db.session` with that tenant_id set, so password
       verification and everything downstream happens against a
       properly RLS-governed, ORM-managed object.
    """
    if not email or not password:
        return None

    index_row = EmailTenantIndex.query.filter_by(email=email).first()
    if not index_row:
        return None

    with db.session.begin_nested():
        db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(index_row.tenant_id)})
        user = db.session.get(User, index_row.user_id)

    if not user or user.status != "active":
        return None

    # Real enforcement, not cosmetic -- set only by a real platform
    # admin (app/platform_admin/services.py:suspend_tenant). `tenants`
    # has no RLS at all, so this read needs no tenant context.
    tenant = Tenant.query.filter_by(id=index_row.tenant_id).first()
    if tenant and tenant.is_suspended:
        return None

    try:
        _hasher.verify(user.password_hash, password)
    except VerifyMismatchError:
        return None

    return user


def revoke_refresh_token(jti: str, *, expires_in_seconds: int) -> None:
    """
    Marks a refresh token JTI as revoked in Redis, with a TTL matching
    the token's own remaining lifetime -- there's no reason to remember
    a revocation past the point the token would have expired on its
    own anyway, and a fixed TTL keeps the blocklist from growing
    without bound as users log out over time.
    """
    from app.extensions import get_redis_client

    get_redis_client().set(f"revoked_jti:{jti}", "1", ex=max(expires_in_seconds, 1))


def is_token_revoked(jti: str) -> bool:
    from app.extensions import get_redis_client

    return get_redis_client().exists(f"revoked_jti:{jti}") == 1
