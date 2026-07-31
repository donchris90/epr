"""
Seeds realistic data volume for backend/loadtest/locustfile.py.
Not idempotent by design -- run against a disposable dev database,
never production. Deletes any prior run's data for the same fixed
tenant ID first.

Usage:
    DATABASE_URL=... SECRET_KEY=... JWT_SECRET_KEY=... REDIS_URL=... \\
        python loadtest/seed.py
"""
from app import create_app
from app.extensions import db
from sqlalchemy import text
from app.auth.jwt_utils import hash_password

TENANT = "55555555-5555-5555-5555-555555555555"
PASSWORD = "correct horse battery staple"
NUM_USERS = 20  # distinct real users, so the per-user rate-limit key
                # (app/extensions.py:_rate_limit_key) is genuinely
                # exercised the way many different people on one
                # office network would use it.

app = create_app("development")

with app.app_context():
    db.session.execute(text("DELETE FROM tenants WHERE id = :t"), {"t": TENANT})
    db.session.commit()

    db.session.execute(text("INSERT INTO tenants (id, name) VALUES (:t, 'Load Test Co')"), {"t": TENANT})
    db.session.commit()
    db.session.execute(text("SET LOCAL app.tenant_id = :t"), {"t": TENANT})

    from app.models.core import Role, User

    role = Role(tenant_id=TENANT, name="Administrator", permission_set=["*"])
    db.session.add(role)
    db.session.flush()

    for i in range(1, NUM_USERS + 1):
        db.session.add(User(
            tenant_id=TENANT, email=f"loadtest{i}@example.com",
            password_hash=hash_password(PASSWORD), role_id=role.id, status="active",
        ))
    db.session.commit()

    db.session.execute(text("SET LOCAL app.tenant_id = :t"), {"t": TENANT})
    from app.modules.bdc.models import Client
    for i in range(200):
        db.session.add(Client(tenant_id=TENANT, name=f"Client {i}", billing_email=f"client{i}@example.com"))
    db.session.commit()

    db.session.execute(text("SET LOCAL app.tenant_id = :t"), {"t": TENANT})
    from app.modules.prc.models import Vendor
    for i in range(150):
        db.session.add(Vendor(tenant_id=TENANT, name=f"Vendor {i}"))
    db.session.commit()

    db.session.execute(text("SET LOCAL app.tenant_id = :t"), {"t": TENANT})
    from app.modules.inv.models import MaterialItem
    for i in range(300):
        db.session.add(MaterialItem(tenant_id=TENANT, code=f"MAT-{i:04d}", description=f"Material item {i}", unit="units"))
    db.session.commit()

    print(f"Seeded tenant {TENANT}: {NUM_USERS} users, 200 clients, 150 vendors, 300 material items.")
    print(f"All users share password: {PASSWORD}")
