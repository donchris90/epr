"""
One-time platform admin bootstrap, meant to be called from
docker-entrypoint.sh on deploy -- NOT a Flask CLI command and NOT an
API endpoint. See app/platform_admin/services.py's create_platform_admin
docstring and migrations/versions/0039_platform_admin.py for why this
project deliberately keeps platform-admin creation out of both of
those.

This script is the narrow exception: it only runs where you already
have full control of the environment (Render's env var dashboard, not
committed to git, not reachable over HTTP), and it's a safe no-op in
every case except "no platform admin exists yet and both env vars are
set" -- so it's safe to leave wired into every deploy indefinitely.

Required env vars (set these in Render's dashboard, NOT in render.yaml,
so they never end up in git):
    PLATFORM_ADMIN_BOOTSTRAP_EMAIL
    PLATFORM_ADMIN_BOOTSTRAP_PASSWORD

Behavior:
    - If either env var is unset: prints a message and exits 0 (no-op).
      This is the steady-state after you've bootstrapped once and
      cleared the password var.
    - If a platform admin already exists (any email, any status):
      prints a message and exits 0 (no-op). This is what makes it safe
      to run on every deploy -- it will never create a second admin
      or overwrite anything.
    - Otherwise: creates the admin via the same create_platform_admin()
      service function the `flask create-platform-admin` CLI command
      uses, so the password hash is produced identically (Argon2id,
      see app/auth/jwt_utils.py).

Recommended usage:
    1. Set both env vars in Render's dashboard for siteforge-api.
    2. Deploy. Check the deploy logs to confirm "Created platform
       admin: ...".
    3. Delete PLATFORM_ADMIN_BOOTSTRAP_PASSWORD from Render's dashboard
       (leaving the email var is harmless, but the password no longer
       needs to sit there once the account exists).
"""
import os
import sys

from app import create_app
from app.extensions import db
from app.platform_admin.models import PlatformAdmin
from app.platform_admin.services import create_platform_admin


def main():
    email = os.environ.get("PLATFORM_ADMIN_BOOTSTRAP_EMAIL")
    password = os.environ.get("PLATFORM_ADMIN_BOOTSTRAP_PASSWORD")

    if not email or not password:
        print("bootstrap_platform_admin: env vars not set, skipping (no-op).")
        return

    app = create_app()
    with app.app_context():
        if db.session.query(PlatformAdmin.query.exists()).scalar():
            print("bootstrap_platform_admin: a platform admin already exists, skipping (no-op).")
            return

        if len(password) < 8:
            print("bootstrap_platform_admin: PLATFORM_ADMIN_BOOTSTRAP_PASSWORD must be "
                  "at least 8 characters -- skipping this run.", file=sys.stderr)
            return

        admin = create_platform_admin(email, password)
        print(f"bootstrap_platform_admin: created platform admin {admin.email} ({admin.id}).")
        print("bootstrap_platform_admin: you can now remove PLATFORM_ADMIN_BOOTSTRAP_PASSWORD "
              "from Render's env vars -- this script is a no-op from here on.")


if __name__ == "__main__":
    main()
