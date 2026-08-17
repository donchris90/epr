#!/bin/sh
# Baked into the image deliberately, not passed via Render's
# dockerCommand field -- a real deploy proved Render doesn't reliably
# shell-interpret that field (it appears to space-split the command
# string directly rather than running it through a shell), which
# broke a plain "flask db upgrade && gunicorn ..." chain, and left it
# genuinely unclear whether an explicit `sh -c "..."` wrapper would
# survive that same splitting intact. A single script path passed as
# CMD has no internal whitespace to be mis-split by anything upstream
# of Docker itself, which sidesteps the ambiguity entirely rather than
# gambling on it.
set -e

echo "Running database migrations..."
flask db upgrade

echo "Checking platform admin bootstrap..."
python scripts/bootstrap_platform_admin.py

echo "Starting gunicorn..."
exec gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
