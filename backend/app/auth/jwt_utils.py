"""
Authentication helpers: password verification and refresh-token revocation.
Passwords are hashed with Argon2id (SRS Section 10.4) -- no plaintext or
reversibly-encrypted password storage.
"""
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import text

from app.extensions import get_auth_engine, db
from app.models.core import User

_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    return _hasher.hash(plain_password)


def authenticate_user(email: str, password: str):
    """
    Two-step lookup, deliberately:

    1. Find the user's tenant_id by email using the narrowly-privileged
       auth engine (BYPASSRLS, SELECT-only on `users` -- see
       app/extensions.py:get_auth_engine). This is the ONLY place in the
       app that queries `users` outside of a tenant context, because
       it's the only place that has to: login doesn't know the tenant
       yet, and RLS + FORCE correctly prevents the normal tenant-scoped
       session from doing this lookup at all.
    2. Once the tenant is known, re-fetch the row through the normal
       tenant-scoped `db.session` with that tenant_id set, so password
       verification and everything downstream happens against a
       properly RLS-governed, ORM-managed object -- not one fetched
       through the bypass path.
    """
    if not email or not password:
        return None

    with get_auth_engine().connect() as conn:
        row = conn.execute(
            text("SELECT id, tenant_id FROM users WHERE email = :email AND status = 'active'"),
            {"email": email},
        ).first()

    if not row:
        return None

    with db.session.begin_nested():
        db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(row.tenant_id)})
        user = db.session.get(User, row.id)

    if not user:
        return None  # defensive: row existed via bypass but vanished under RLS (shouldn't happen)

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
