#!/usr/bin/env bash
# Real, runnable Postgres backup script -- not just documentation.
#
# Usage: DATABASE_URL=postgresql://user:pass@host:5432/dbname ./backup.sh [output_dir]
#
# Produces a timestamped, compressed pg_dump in custom format
# (-Fc), which supports both full and selective restore (pg_restore
# --table=... for pulling back a single table without touching the
# rest of the database) and is what restore.sh in this same directory
# expects.
set -euo pipefail

OUTPUT_DIR="${1:-./backups}"
mkdir -p "$OUTPUT_DIR"

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is required (postgresql://user:pass@host:port/dbname)" >&2
  exit 1
fi

TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
OUTPUT_FILE="${OUTPUT_DIR}/siteforge-${TIMESTAMP}.dump"

echo "Backing up to ${OUTPUT_FILE} ..."
pg_dump "$DATABASE_URL" -Fc -f "$OUTPUT_FILE"

echo "Verifying the dump is actually readable (not just written) ..."
pg_restore --list "$OUTPUT_FILE" > /dev/null

SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
echo "Backup complete: ${OUTPUT_FILE} (${SIZE})"

# Off-host copy: local-disk-only backups don't survive the loss of the
# host they were taken on. SKIP_S3_UPLOAD=1 bypasses this for a local
# dev backup where no S3 endpoint is configured (or reachable) at all.
if [ "${SKIP_S3_UPLOAD:-0}" != "1" ]; then
  echo "Uploading to off-host object storage ..."
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
  BACKEND_ROOT="$(dirname "$SCRIPT_DIR")"
  # PYTHONPATH must include the backend root, not just the scripts/
  # directory Python adds automatically -- "from app import
  # create_app" in upload_backup_to_s3.py otherwise fails no matter
  # what directory this script itself is invoked from.
  PYTHONPATH="$BACKEND_ROOT:${PYTHONPATH:-}" python "$SCRIPT_DIR/upload_backup_to_s3.py" "$OUTPUT_FILE"
else
  echo "SKIP_S3_UPLOAD=1 set -- backup exists only on local disk."
fi

# Retention: keep the last 30 daily backups in this directory, delete
# anything older. This only prunes the LOCAL copy -- the S3 copy above
# has its own lifecycle policy to manage separately (bucket-level
# lifecycle rules, not this script), since the two serve different
# purposes: local disk is for a fast same-host restore, S3 is what
# survives the host being lost entirely.
find "$OUTPUT_DIR" -name "siteforge-*.dump" -mtime +30 -delete
