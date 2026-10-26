"""
Notifications service layer.
"""
from datetime import datetime, timezone

from app.extensions import db
from app.notifications.models import (
    NOTIFICATION_CATEGORIES,
    Notification,
    NotificationPreference,
    category_for_type,
)


def notify(tenant_id, *, user_id, type, title, body=None, data=None, channel="in_app"):
    """Creates and persists one notification. Deliberately does not
    commit -- callers that create a notification alongside some other
    real state change (e.g. app/workflow/services.py advancing a
    workflow instance) should commit both together in one transaction,
    so a notification is never recorded for a state change that then
    fails to persist, and vice versa. A caller that only wants to
    notify with nothing else to commit should call db.session.commit()
    itself right after."""
    in_app_on, email_on = _channel_flags(tenant_id, user_id, type)

    notification = None
    if in_app_on:
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

    # Email is only sent when the caller asked for it (channel != in_app)
    # and the recipient has not switched it off for this category. This
    # holds even when the in-app row is suppressed.
    if channel != "in_app" and email_on:
        _dispatch_external(tenant_id, user_id, title, body, notification.id if notification else None)

    return notification


def notify_many(tenant_id, *, user_ids, type, title, body=None, data=None, channel="in_app"):
    """The common case for a role-resolved audience (e.g. every user
    holding the role a workflow step requires) -- one notification row
    per recipient, not a single shared row, so each person's own
    read/unread state is independent."""
    results = [
        notify(tenant_id, user_id=uid, type=type, title=title, body=body, data=data, channel=channel)
        for uid in user_ids
    ]
    # A recipient who switched in-app off for this category gets no row.
    return [n for n in results if n is not None]


def _dispatch_external(tenant_id, user_id, title, body, notification_id=None) -> None:
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

    user = User.query.filter_by(tenant_id=tenant_id, id=user_id).first()
    if not user or not user.email:
        return

    from app.notifications.tasks import send_email_notification

    try:
        send_email_notification.delay(to_address=user.email, subject=title, body=body or "")
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
            "Notification %s: the email failed to send/queue for %s", notification_id, user.email, exc_info=True
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


# ---------------------------------------------------------------- preferences

def _channel_flags(tenant_id, user_id, notification_type):
    """(in_app_on, email_on) for this recipient and notification type.
    No stored row (including portal users, who have no preferences UI)
    means the default: both on."""
    pref = NotificationPreference.query.filter_by(
        tenant_id=tenant_id, user_id=user_id, category=category_for_type(notification_type)
    ).first()
    if pref is None:
        return True, True
    return pref.in_app, pref.email


def get_preferences(tenant_id, *, user_id):
    """One entry per category, defaults filled in for categories the user
    has never touched."""
    rows = {
        p.category: p
        for p in NotificationPreference.query.filter_by(tenant_id=tenant_id, user_id=user_id).all()
    }
    return [
        {
            "category": c,
            "in_app": rows[c].in_app if c in rows else True,
            "email": rows[c].email if c in rows else True,
        }
        for c in NOTIFICATION_CATEGORIES
    ]


def set_preferences(tenant_id, *, user_id, items):
    """Upsert the given categories (others untouched). Commits."""
    existing = {
        p.category: p
        for p in NotificationPreference.query.filter_by(tenant_id=tenant_id, user_id=user_id).all()
    }
    for item in items:
        pref = existing.get(item["category"])
        if pref is None:
            pref = NotificationPreference(tenant_id=tenant_id, user_id=user_id, category=item["category"])
            db.session.add(pref)
        pref.in_app = item["in_app"]
        pref.email = item["email"]
    db.session.commit()
    return get_preferences(tenant_id, user_id=user_id)


def user_ids_with_permission(tenant_id, permission):
    """Active staff users whose role grants `permission` (or the "*"
    wildcard, matching app/utils/decorators.require_permission)."""
    from app.models.core import Role, User

    role_ids = [
        r.id
        for r in Role.query.filter_by(tenant_id=tenant_id).all()
        if permission in (r.permission_set or []) or "*" in (r.permission_set or [])
    ]
    if not role_ids:
        return []
    users = User.query.filter(
        User.tenant_id == tenant_id, User.role_id.in_(role_ids), User.status == "active"
    ).all()
    return [u.id for u in users]


def notify_users_with_permission(tenant_id, *, permission, type, title, body=None, data=None, channel="in_app"):
    """Notify every active staff user who can act on something (e.g. the
    approvers of a pending request). Does not commit. Pass channel="email"
    to also email them (each user's own preferences can still suppress)."""
    return notify_many(
        tenant_id,
        user_ids=user_ids_with_permission(tenant_id, permission),
        type=type,
        title=title,
        body=body,
        data=data,
        channel=channel,
    )
