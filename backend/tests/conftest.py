"""
Shared pytest fixtures.

IMPORTANT: this suite must run against real PostgreSQL, not SQLite.
The schema uses JSONB columns and Postgres Row-Level Security policies,
neither of which SQLite supports — a passing SQLite run would prove
nothing about the guarantee this suite exists to verify. Point
TEST_DATABASE_URL at a real (disposable) Postgres database, e.g.:

    export TEST_DATABASE_URL=postgresql+psycopg2://siteforge:siteforge@localhost:5432/siteforge_test

The app must also connect as a NON-superuser, non-table-owner role in
this database, or Postgres will silently bypass RLS entirely (both
superusers and table owners bypass RLS by default) and every isolation
test below would give a false pass. See docker-compose.yml / README for
the `siteforge_app` role setup.
"""
import uuid

import pytest
from flask_jwt_extended import create_access_token

from app import create_app
from app.extensions import db as _db


@pytest.fixture(scope="session")
def app():
    app = create_app("testing")
    with app.app_context():
        yield app


def _enable_rls_for_all_tenant_scoped_tables(db):
    """
    `db.create_all()` builds tables from the SQLAlchemy metadata alone —
    it has no idea about Row-Level Security, because RLS is DDL that
    only exists in the Alembic migrations (see migrations/versions/).
    Without this step, every tenant-scoped table in a freshly-created
    test database would have RLS *disabled*, and the isolation tests in
    test_tenant_isolation.py would pass for the wrong reason (or not at
    all) — they'd be testing nothing.

    Walks the actual mapped model classes and applies RLS only to ones
    that mix in TenantMixin -- deliberately NOT "any table with a
    tenant_id-named column," which is a real distinction: a table can
    have a tenant_id column for other reasons (e.g.
    app.models.core.EmailTenantIndex records which tenant a matched
    email belongs to) without being tenant-*scoped* in the RLS sense.
    Applying RLS by column-name alone silently broke EmailTenantIndex
    in this suite the first time it existed -- its entire design point
    is being queryable with zero tenant context, which is exactly what
    FORCE ROW LEVEL SECURITY prevents.
    """
    from sqlalchemy import text
    from app.models.base import TenantMixin

    for mapper in db.Model.registry.mappers:
        model = mapper.class_
        if issubclass(model, TenantMixin):
            table_name = model.__tablename__
            db.session.execute(text(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"))
            # FORCE makes the policy apply even to the table's OWNER.
            # Without it, RLS is silently bypassed whenever the app
            # connects as the same role that ran the migrations (an easy
            # setup to end up in by accident) -- which would make this
            # whole suite pass without testing anything. The same FORCE
            # is applied in production; see migrations/versions/*.py.
            db.session.execute(text(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY"))
            db.session.execute(
                text(
                    f"""
                    CREATE POLICY tenant_isolation ON {table_name}
                    USING (tenant_id = current_setting('app.tenant_id')::uuid)
                    """
                )
            )
    db.session.commit()


@pytest.fixture(scope="function")
def db(app):
    _db.create_all()
    _enable_rls_for_all_tenant_scoped_tables(_db)
    yield _db
    _db.session.remove()
    _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def tenant_ids():
    """Two distinct tenant UUIDs for cross-tenant isolation tests."""
    return {"a": uuid.uuid4(), "b": uuid.uuid4()}


@pytest.fixture()
def seed_tenants(db, tenant_ids):
    """Inserts minimal Tenant rows for both test tenants (tenants table
    itself is not RLS-scoped, so this can run as the app's normal session)."""
    from app.models.core import Tenant

    for key, tid in tenant_ids.items():
        db.session.add(Tenant(id=tid, name=f"Test Tenant {key.upper()}"))
    db.session.commit()
    return tenant_ids


@pytest.fixture()
def real_user(db, seed_tenants):
    """
    A real User row with an actual Argon2 password hash (not a
    create_access_token shortcut) -- for tests that exercise the real
    POST /v1/auth/login -> refresh -> logout HTTP flow end to end,
    rather than assuming a token handed out by the test fixtures
    behaves the same as one the app actually issued. Depends on
    seed_tenants (not the bare tenant_ids dict) because users.tenant_id
    has a real FK constraint to tenants.id.
    """
    from app.auth.jwt_utils import hash_password
    from app.models.core import User, EmailTenantIndex
    from sqlalchemy import text

    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(seed_tenants["a"])})
    user = User(
        tenant_id=seed_tenants["a"],
        email="real-login-test@example.com",
        password_hash=hash_password("correct horse battery staple"),
        status="active",
    )
    db.session.add(user)
    db.session.flush()
    # Login (app/auth/jwt_utils.py:authenticate_user) resolves the
    # tenant via this index, not the users table directly -- a real
    # User row alone isn't enough to log in with anymore.
    db.session.add(EmailTenantIndex(email=user.email, user_id=user.id, tenant_id=seed_tenants["a"]))
    db.session.commit()
    return user


@pytest.fixture()
def auth_headers(app, tenant_ids):
    """
    Returns a factory: auth_headers("a") -> {"Authorization": "Bearer ..."}
    for a JWT scoped to tenant_ids["a"], with full permissions by default.
    """

    def _make(tenant_key: str, *, permissions=None, user_id=None):
        with app.app_context():
            uid = user_id or uuid.uuid4()
            token = create_access_token(
                identity=str(uid),
                additional_claims={
                    "tenant_id": str(tenant_ids[tenant_key]),
                    "user_id": str(uid),
                    "role_id": None,
                    "permissions": permissions if permissions is not None else ["*"],
                },
            )
        return {"Authorization": f"Bearer {token}"}

    return _make
