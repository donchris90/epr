-- One-time setup for the dedicated login-lookup role (see
-- app/extensions.py:get_auth_engine and app/auth/jwt_utils.py for why
-- this role exists).
--
-- `users` is FORCE ROW LEVEL SECURITY protected, correctly -- but login
-- has to find a user by email BEFORE it knows which tenant they belong
-- to, and RLS has no way to authorize a query with no tenant context.
-- This role is a narrow, auditable exception: it can read `users`
-- across every tenant, and NOTHING else. It must never be used for any
-- query except the pre-authentication email lookup.
--
-- Run this once per environment (not via Alembic -- roles are
-- cluster-level, not database-level, so they don't belong in versioned
-- per-database migrations). Set AUTH_DATABASE_URL in .env to use it:
--   AUTH_DATABASE_URL=postgresql+psycopg2://siteforge_auth:<password>@host:5432/siteforge

CREATE ROLE siteforge_auth WITH LOGIN PASSWORD 'change-me-in-production' BYPASSRLS;

GRANT CONNECT ON DATABASE siteforge TO siteforge_auth;
GRANT USAGE ON SCHEMA public TO siteforge_auth;

-- SELECT only, and only the columns the lookup actually needs -- not
-- password_hash, not anything else. A view enforces this even if a
-- future query against this role gets sloppy.
CREATE VIEW auth_user_lookup AS
    SELECT id, tenant_id, email, status FROM users;

GRANT SELECT ON auth_user_lookup TO siteforge_auth;
GRANT SELECT ON users TO siteforge_auth;  -- used directly for now; see note below

-- NOTE: app/auth/jwt_utils.py currently selects id/tenant_id directly
-- from `users` for simplicity. Switching that query to select from
-- `auth_user_lookup` instead and revoking the direct `users` grant
-- above is a straightforward follow-up hardening step -- both exist so
-- that migration can happen without a coordinated code+SQL deploy.
