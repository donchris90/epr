"""
Authentication helpers: password verification and refresh-token revocation.
Passwords are hashed with Argon2id (SRS Section 10.4) -- no plaintext or
reversibly-encrypted password storage.
"""
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import text

from app.extensions import db
from app.models.core import User, EmailTenantIndex

_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    return _hasher.hash(plain_password)


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
