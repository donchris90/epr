"""
Notifications service layer.
"""
from datetime import datetime, timezone

from app.extensions import db
from app.notifications.models import Notification


def notify(tenant_id, *, user_id, type, title, body=None, data=None, channel="in_app"):
    """Creates and persists one notification. Deliberately does not
    commit -- callers that create a notification alongside some other
    real state change (e.g. app/workflow/services.py advancing a
    workflow instance) should commit both together in one transaction,
    so a notification is never recorded for a state change that then
    fails to persist, and vice versa. A caller that only wants to
    notify with nothing else to commit should call db.session.commit()
    itself right after."""
    notification = Notification(
        tenant_id=tenant_id,
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        data=data or {},
        channel=channel,
    )
    db.session.add(notification)

    if channel != "in_app":
        _dispatch_external(notification)

    return notification


def notify_many(tenant_id, *, user_ids, type, title, body=None, data=None, channel="in_app"):
    """The common case for a role-resolved audience (e.g. every user
    holding the role a workflow step requires) -- one notification row
    per recipient, not a single shared row, so each person's own
    read/unread state is independent."""
    return [
        notify(tenant_id, user_id=uid, type=type, title=title, body=body, data=data, channel=channel)
        for uid in user_ids
    ]


def _dispatch_external(notification: Notification) -> None:
    """
    Queues a real email via Celery -- never sends inline here, so a
    slow or down SMTP server can never block the request that
    triggered the notification (see app/notifications/tasks.py for
    why the task takes plain values rather than re-querying this row).

    Looks up the recipient's real email address now, synchronously,
    within the caller's own transaction/tenant context -- this is a
    fast, indexed, tenant-scoped read, not a network call, so it's
    safe to do inline. `notification.user_id` is a loose reference
    (not every module this integrates with necessarily has a matching
    `users` row -- e.g. a future integration notifying a portal user
    instead of an internal one), so a missing user is a real,
    unremarkable case, not an error: there's simply nowhere to send
    an email, and this silently does nothing rather than raising.
    """
    from app.models.core import User

    user = User.query.filter_by(tenant_id=notification.tenant_id, id=notification.user_id).first()
    if not user or not user.email:
        return

    from app.notifications.tasks import send_email_notification

    try:
        send_email_notification.delay(to_address=user.email, subject=notification.title, body=notification.body or "")
    except Exception:
        # Same real bug, same real fix as
        # app/org/services.py:_send_invitation_email -- with
        # CELERY_TASK_ALWAYS_EAGER on (see app/config.py's own note),
        # a failed send's retry-on-failure logic
        # (app/notifications/tasks.py) raises synchronously right
        # here, and this function is called from real business
        # actions across this codebase (workflow approvals, among
        # others, via app/workflow/services.py) -- a failed
        # notification email must never crash or roll back whatever
        # real action actually triggered it.
        import logging

        logging.getLogger(__name__).warning(
            "Notification %s created but the email failed to send/queue for %s", notification.id, user.email, exc_info=True
        )


def list_for_user(tenant_id, *, user_id, unread_only=False, cursor=None, limit=50):
    query = Notification.query.filter_by(tenant_id=tenant_id, user_id=user_id)
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    if cursor:
        query = query.filter(Notification.created_at < cursor)
    return query.order_by(Notification.created_at.desc()).limit(limit).all()


def count_unread(tenant_id, *, user_id):
    return Notification.query.filter_by(tenant_id=tenant_id, user_id=user_id, read_at=None).count()


def mark_read(notification: Notification):
    notification.read_at = datetime.now(timezone.utc)
    db.session.commit()
    return notification


def mark_unread(notification: Notification):
    notification.read_at = None
    db.session.commit()
    return notification


def mark_all_read(tenant_id, *, user_id):
    now = datetime.now(timezone.utc)
    Notification.query.filter_by(tenant_id=tenant_id, user_id=user_id, read_at=None).update({"read_at": now})
    db.session.commit()
