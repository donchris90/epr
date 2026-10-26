# Running SiteForge on Supabase Postgres

SiteForge only needs a plain Postgres 15/16 database. Supabase is used purely
as a host: no Supabase Auth, Storage or PostgREST. Tenant isolation is
SiteForge's own Row-Level Security (`SET LOCAL app.tenant_id`).

## 1. Create the project
Supabase dashboard > New project. Save the database password (avoid `@ : / ? #`
or URL-encode them, e.g. `@` -> `%40`).

## 2. Create a dedicated application role (important)
Supabase's default `postgres` role has **BYPASSRLS**, so connecting as it would
silently disable SiteForge's tenant isolation. Run once in the SQL editor:

```sql
create role siteforge_app login password 'CHOOSE-A-STRONG-PASSWORD'
  nosuperuser nobypassrls nocreatedb nocreaterole;
grant usage, create on schema public to siteforge_app;
grant all on all tables in schema public to siteforge_app;
grant all on all sequences in schema public to siteforge_app;
alter default privileges in schema public grant all on tables to siteforge_app;
alter default privileges in schema public grant all on sequences to siteforge_app;
```

The role that runs migrations should own the tables, so use `siteforge_app`
for BOTH migrations and the running app (tables it creates, it owns; FORCE ROW
LEVEL SECURITY then applies to it, which is what we want).

## 3. Connection string
Use the **Session pooler** (Dashboard > Connect > Session pooler, port 5432).
Render cannot reach Supabase's direct `db.<ref>.supabase.co` host (IPv6 only).

```
postgresql+psycopg2://siteforge_app.<PROJECT_REF>:<PASSWORD>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require
```

Note the user is `siteforge_app.<PROJECT_REF>` (role + project ref).
Do not use the Transaction pooler (6543) for migrations.

## 4. Render
Set `DATABASE_URL` to that string on every service that lists it (API, workers,
cron jobs). Redeploy; the start command runs `flask db upgrade`.

## 5. Verify
```sql
select rolname, rolbypassrls, rolsuper from pg_roles where rolname='siteforge_app'; -- both false
select count(*) from alembic_version;                                                -- 1 row
```
