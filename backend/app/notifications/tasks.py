"""
Celery tasks for Notifications.

send_email_notification takes the recipient address, subject, and body
as plain arguments rather than a notification_id to look up -- this is
deliberate, not a shortcut. If it took an ID and re-queried the
Notification row, there would be a real race: .delay() can hand the
task to a worker before the calling request's own transaction has
committed, so the row might not exist yet when the task runs. Passing
everything the task actually needs as plain values sidesteps that
entirely -- this task never touches the database at all, so there's
nothing for it to race against.
"""
import logging

from app.extensions import celery
from app.notifications.email import send_email

logger = logging.getLogger(__name__)


@celery.task(name="notifications.send_email", bind=True, max_retries=3, default_retry_delay=30)
def send_email_notification(self, *, to_address: str, subject: str, body: str):
    """
    Real retry behavior for transient failures (SMTP server briefly
    unreachable, rate-limited, etc.) -- up to 3 attempts, 30 seconds
    apart, for a genuine async worker. send_email() itself never
    raises (it catches SMTP/OSError and returns False), so this task
    has to explicitly decide a False result is worth retrying; a
    permanently-unconfigured SMTP setup (no username/password) also
    returns False, and retrying that would just waste 3 attempts
    before giving up anyway, which is fine -- it's a rare, static
    state, not a hot path.

    Real fix found from a live production hang, not by inspection:
    self.request.is_eager is True whenever CELERY_TASK_ALWAYS_EAGER is
    on (Render's free tier, no separate worker service -- see
    app/config.py's own note), meaning this whole task runs
    synchronously inside the calling HTTP request with no async
    boundary at all. In that mode, self.retry() doesn't queue a real
    future attempt -- it just raises immediately, and if the CALLER
    that already caught this exception once (app/org/services.py,
    app/notifications/services.py) is later changed and stops
    catching it, or something else invokes this task directly, a real
    retry loop here would mean the SAME blocked request pays for the
    full SMTP timeout up to 3 additional times before ever getting a
    response -- exactly what "the browser gave up waiting" looks like
    from the outside. Retrying only makes sense when a real worker,
    running outside any request, can afford to wait and try later.
    """
    sent = send_email(to_address=to_address, subject=subject, body=body)
    if not sent:
        if self.request.is_eager:
            logger.warning(
                "Email dispatch failed for %r to %s (eager mode -- not retrying synchronously)", subject, to_address
            )
            return {"sent": False, "to": to_address}
        raise self.retry(exc=RuntimeError(f"Email dispatch failed for {to_address!r}: {subject!r}"))
    return {"sent": True, "to": to_address}
