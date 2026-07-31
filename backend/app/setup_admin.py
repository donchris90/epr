"""
One-time production setup endpoint -- creates the dedicated
BYPASSRLS auth-lookup role (backend/scripts/setup_auth_role.sql)
using this app's own already-working database connection, so no
separate database client or connection string is needed at all.

SECURITY: this is deliberately temporary. Set SETUP_SECRET, use the
endpoint once, then remove both the env var and (ideally) this file
and its blueprint registration in app/__init__.py. Every request
requires the exact secret as a query parameter; with SETUP_SECRET
unset (the default), every request is refused regardless of what's
supplied.
"""
import secrets

from flask import Blueprint, jsonify, request, current_app
from sqlalchemy import text

from app.extensions import db

bp = Blueprint("setup_admin", __name__, url_prefix="/v1/_setup")


@bp.get("/auth-role")
def create_auth_role():
    configured_secret = current_app.config.get("SETUP_SECRET", "")
    supplied_secret = request.args.get("secret", "")

    if not configured_secret or not secrets.compare_digest(supplied_secret, configured_secret):
        # Deliberately the same generic 404 whether SETUP_SECRET is
        # unset or the supplied secret is simply wrong -- doesn't
        # confirm to an outside prober that this route exists at all.
        return jsonify({"error": "not found"}), 404

    role_password = secrets.token_urlsafe(24)
    # Safe to interpolate directly despite generally being bad
    # practice: this value is server-generated via secrets.token_urlsafe
    # (URL-safe base64 alphabet only -- never a quote character), not
    # user input, and PostgreSQL's CREATE ROLE / ALTER ROLE ... WITH
    # PASSWORD don't accept bind parameters for this position anyway
    # (a DDL-level limitation, not a shortcut taken here).

    with db.engine.connect() as conn:
        current_db = conn.execute(text("SELECT current_database()")).scalar()

        role_exists = conn.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = 'siteforge_auth'")
        ).scalar()

        if role_exists:
            # Idempotent: if it already exists, just reset the
            # password so this endpoint can be safely re-run (e.g. if
            # the first AUTH_DATABASE_URL value got lost) without a
            # confusing "role already exists" failure.
            conn.execute(text(f"ALTER ROLE siteforge_auth WITH PASSWORD '{role_password}'"))
        else:
            conn.execute(
                text(f"CREATE ROLE siteforge_auth WITH LOGIN PASSWORD '{role_password}' BYPASSRLS")
            )

        conn.execute(text(f'GRANT CONNECT ON DATABASE "{current_db}" TO siteforge_auth'))
        conn.execute(text("GRANT USAGE ON SCHEMA public TO siteforge_auth"))
        conn.execute(text("GRANT SELECT ON users TO siteforge_auth"))
        conn.commit()

        # Build the exact value to paste into AUTH_DATABASE_URL,
        # reusing this same connection's own host/port -- so nothing
        # needs to be typed or guessed by hand.
        host = conn.engine.url.host
        port = conn.engine.url.port or 5432

    auth_database_url = f"postgresql+psycopg2://siteforge_auth:{role_password}@{host}:{port}/{current_db}"

    return jsonify({
        "status": "done",
        "next_step": "Copy the auth_database_url value below into siteforge-api's Environment tab as AUTH_DATABASE_URL, save, redeploy -- then remove SETUP_SECRET and this endpoint.",
        "auth_database_url": auth_database_url,
    })
