"""
Celery worker entrypoint. Run with:
    celery -A app.celery_app.celery worker --loglevel=info

Handles background jobs: report generation, AI Assistant calls,
notification fan-out, scheduled reorder/expiry checks (SRS Section 3.1/13.2).
"""
from app import create_app
from app.extensions import celery


def init_celery(app):
    celery.conf.update(
        broker_url=app.config["CELERY_BROKER_URL"],
        result_backend=app.config["CELERY_RESULT_BACKEND"],
        # Runs once a day -- see app/modules/inv/tasks.py for why a
        # daily cadence (paired with that task's own 7-day per-item
        # cooldown) is the right frequency: frequent enough to catch a
        # new shortage promptly, infrequent enough that the cooldown
        # rarely even needs to suppress a duplicate in practice.
        beat_schedule={
            "check-reorder-levels-daily": {
                "task": "inv.check_and_create_reorder_purchase_requests",
                "schedule": 60 * 60 * 24,
            },
        },
    )

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery


flask_app = create_app()
celery = init_celery(flask_app)

# Task modules are imported here (inside the app context established
# above) so Celery's task registry picks up every @celery.task
# definition when this module loads -- whether that's the worker
# process (`celery -A app.celery_app.celery worker`) or the beat
# scheduler (`celery -A app.celery_app.celery beat`).
with flask_app.app_context():
    from app.modules.inv import tasks as inv_tasks  # noqa: F401
