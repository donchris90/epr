"""billing plans and subscriptions

Revision ID: 0038_billing_plans
Revises: 0037_est_revision_status
Create Date: 2026-08-17

Real subscription billing: platform-defined plan catalog
(subscription_plans, not tenant-scoped, no RLS -- reference data
every tenant needs to see, matching `tenants` itself) and per-tenant
subscription state (tenant_subscriptions, tenant-scoped, real RLS,
matching every other tenant-owned table).

Seeds 3 starter plans with placeholder NGN pricing -- these are
deliberately round, clearly-adjustable numbers, not real business
pricing decisions made on the user's behalf. Edit the seeded rows
directly (or add a real admin endpoint later) before this matters in
production.

Backfills every EXISTING tenant with a grandfathered, permanently
active subscription (status="active", no trial_ends_at, no
current_period_end, no real payment ever collected) -- preserving
current behavior for every tenant created before this feature existed
rather than retroactively putting them on a 14-day trial clock they
never agreed to. New tenants signing up after this migration get a
real 14-day trial (see app/onboarding/services.py's integration).
"""
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0038_billing_plans"
down_revision = "0037_est_revision_status"
branch_labels = None
depends_on = None

DEFAULT_TRIAL_PLAN_CODE = "growth"  # see app/billing/services.py -- the plan a new trial defaults to


def upgrade():
    op.create_table(
        "subscription_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("monthly_price_ngn", sa.Numeric(12, 2), nullable=False),
        sa.Column("annual_price_ngn", sa.Numeric(12, 2), nullable=False),
        sa.Column("seat_limit", sa.Integer, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.create_table(
        "tenant_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subscription_plans.id"), nullable=False),
        sa.Column("billing_cycle", sa.String(16), nullable=False, server_default="monthly"),
        sa.Column("status", sa.String(16), nullable=False, server_default="trialing"),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paystack_customer_code", sa.String(64), nullable=True),
        sa.Column("paystack_subscription_code", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("billing_cycle IN ('monthly', 'annual')", name="ck_tenant_subscriptions_cycle"),
        sa.CheckConstraint(
            "status IN ('trialing', 'active', 'past_due', 'canceled', 'expired')",
            name="ck_tenant_subscriptions_status",
        ),
        sa.UniqueConstraint("tenant_id", name="uq_tenant_subscriptions_one_per_tenant"),
    )
    op.execute("ALTER TABLE tenant_subscriptions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_subscriptions FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON tenant_subscriptions "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )

    connection = op.get_bind()

    # Seed the plan catalog -- real, placeholder pricing (see this
    # file's own docstring); PLATFORM data, no RLS, no per-tenant
    # SET LOCAL needed for this insert.
    plans = [
        {"id": str(uuid.uuid4()), "code": "starter", "name": "Starter", "monthly": 25000, "annual": 250000, "seats": 5},
        {"id": str(uuid.uuid4()), "code": "growth", "name": "Growth", "monthly": 75000, "annual": 750000, "seats": 20},
        {"id": str(uuid.uuid4()), "code": "enterprise", "name": "Enterprise", "monthly": 200000, "annual": 2000000, "seats": None},
    ]
    for p in plans:
        connection.execute(
            sa.text(
                "INSERT INTO subscription_plans (id, code, name, monthly_price_ngn, annual_price_ngn, seat_limit, is_active) "
                "VALUES (:id, :code, :name, :monthly, :annual, :seats, true)"
            ),
            p,
        )

    growth_plan_id = next(p["id"] for p in plans if p["code"] == DEFAULT_TRIAL_PLAN_CODE)

    # Backfill: every existing tenant gets a grandfathered, permanently
    # active subscription -- looping per-tenant with real SET LOCAL,
    # not one bare cross-tenant statement, matching the exact,
    # previously-learned lesson from migration 0030's own history
    # (tenant_subscriptions has FORCE RLS just applied above).
    tenant_ids = [row[0] for row in connection.execute(sa.text("SELECT id FROM tenants")).fetchall()]
    for tenant_id in tenant_ids:
        connection.execute(sa.text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})
        connection.execute(
            sa.text(
                "INSERT INTO tenant_subscriptions (id, tenant_id, plan_id, billing_cycle, status) "
                "VALUES (:id, :tid, :plan_id, 'monthly', 'active')"
            ),
            {"id": str(uuid.uuid4()), "tid": str(tenant_id), "plan_id": growth_plan_id},
        )


def downgrade():
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tenant_subscriptions")
    op.drop_table("tenant_subscriptions")
    op.drop_table("subscription_plans")
