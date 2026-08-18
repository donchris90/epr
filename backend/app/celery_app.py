"""
Celery worker entrypoint. Run with:
    celery -A app.celery_app.celery worker --loglevel=info

Handles background jobs: report generation, AI Assistant calls,
notification fan-out, scheduled reorder/expiry checks (SRS Section 3.1/13.2).

Configuration itself now lives in app/extensions.py:configure_celery,
shared with app/__init__.py's create_app() -- previously duplicated
here only, which meant the actual web service (gunicorn running
wsgi:app) never configured Celery's broker/result backend at all. See
that function's own docstring for the real bug this fixed.
"""
from app import create_app
from app.extensions import celery, configure_celery

flask_app = create_app()
configure_celery(flask_app)

# Task modules are imported here (inside the app context established
# above) so Celery's task registry picks up every @celery.task
# definition when this module loads -- whether that's the worker
# process (`celery -A app.celery_app.celery worker`) or the beat
# scheduler (`celery -A app.celery_app.celery beat`).
with flask_app.app_context():
    from app.modules.inv import tasks as inv_tasks  # noqa: F401
    from app.modules.eqp import tasks as eqp_tasks  # noqa: F401
    from app.notifications import tasks as notification_tasks  # noqa: F401
