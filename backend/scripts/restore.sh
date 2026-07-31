#!/usr/bin/env bash
# Restores a backup produced by backup.sh into a target database.
#
# Usage: DATABASE_URL=postgresql://user:pass@host:5432/target_dbname ./restore.sh path/to/siteforge-TIMESTAMP.dump
#
# Deliberately restores into whatever database DATABASE_URL points at
# -- for a real disaster-recovery drill, that should be a FRESH,
# empty database, never the live one directly, so the drill itself
# can't corrupt production data if something goes wrong partway
# through. Promote the restored database to "live" only after the
# restore is verified (see the verification queries below).
set -euo pipefail

DUMP_FILE="${1:-}"

if [ -z "$DUMP_FILE" ] || [ ! -f "$DUMP_FILE" ]; then
  echo "Usage: DATABASE_URL=... ./restore.sh path/to/backup.dump" >&2
  exit 1
fi

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is required (postgresql://user:pass@host:port/dbname)" >&2
  exit 1
fi

echo "Restoring ${DUMP_FILE} into the database at DATABASE_URL ..."
pg_restore -d "$DATABASE_URL" --clean --if-exists --no-owner --no-privileges "$DUMP_FILE"

echo ""
echo "Restore finished. Run these BEFORE treating this database as trustworthy:"
echo "  1. Row-level security is real, not just present:"
echo "     psql \"\$DATABASE_URL\" -c \"SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'documents';\""
echo "     (expect relrowsecurity=t, relforcerowsecurity=t)"
echo "  2. Tenant count looks sane (compare against the source environment):"
echo "     psql \"\$DATABASE_URL\" -c \"SELECT count(*) FROM tenants;\""
echo "  3. The app's own migration state matches what's expected:"
echo "     cd backend && DATABASE_URL=\$DATABASE_URL flask db current"
