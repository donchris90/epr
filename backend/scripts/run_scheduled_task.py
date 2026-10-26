"""
Run ONE scheduled Celery task to completion, in-process, then exit.

Why this exists
---------------
The beat schedule (app/extensions.py:configure_celery) defines WHAT
should run daily, but production has nothing that triggers it: Render's
free tier has no background-worker service, and a long-running
`celery beat` process needs one. Render Cron Jobs are the supported
alternative -- each fire starts the same Docker image, runs one command,
and exits. This script is that command: it looks the task up by name,
calls it directly (no broker, no worker -- the ContextTask wrapper
supplies the Flask app context), prints the task's summary as JSON, and
exits non-zero when the task reports per-tenant errors so Render marks
the run as failed instead of silently green.

Usage (from the backend root, which is /srv/app in the image):
    python -m scripts.run_scheduled_task inv.check_and_create_reorder_purchase_requests
    python -m scripts.run_scheduled_task eqp.apply_due_transfer_cutovers

Only task names present in the beat schedule are accepted. A cron job
is a deployment convenience, not a generic remote-execution hook.

Exit codes: 0 ok, 1 task ran but reported errors / raised, 2 bad usage.
"""
import json
import sys


def allowed_task_names(beat_schedule: dict) -> set:
    return {entry["task"] for entry in beat_schedule.values()}


def exit_code_for(result) -> int:
    """Both existing tasks return {..., "errors": [per-tenant failures]}
    instead of raising, so one bad tenant doesn't abort the rest. That
    is right for the task and wrong for a scheduler: a run with any
    errors must still look failed."""
    if isinstance(result, dict) and result.get("errors"):
        return 1
    return 0


def run(task_name: str, beat_schedule: dict, registry: dict) -> int:
    allowed = allowed_task_names(beat_schedule)
    if task_name not in allowed:
        print(f"Unknown or non-scheduled task {task_name!r}. Allowed: {sorted(allowed)}", file=sys.stderr)
        return 2
    task = registry.get(task_name)
    if task is None:
        print(f"Task {task_name!r} is scheduled but not registered with Celery.", file=sys.stderr)
        return 2

    try:
        result = task()
    except Exception as exc:  # noqa: BLE001 -- surface any crash as a failed run
        print(json.dumps({"task": task_name, "status": "crashed", "error": repr(exc)}), file=sys.stderr)
        return 1

    print(json.dumps({"task": task_name, "status": "completed", "result": result}, default=str))
    return exit_code_for(result)


def main(argv: list) -> int:
    if len(argv) != 2:
        print("Usage: python -m scripts.run_scheduled_task <celery.task.name>", file=sys.stderr)
        return 2

    # Imported here, not at module top, so the pure helpers above stay
    # importable (and unit-testable) without building the whole app.
    from app.celery_app import celery

    return run(argv[1], celery.conf.beat_schedule, celery.tasks)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
