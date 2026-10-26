"""
Notifications addressed to external portal users (subcontractor and
vendor portals). Reuses the ordinary `notifications` table and the
/v1/notifications routes: a portal user's id is simply the `user_id`
(a loose reference by design), and the portal token's tenant_id /
user_id claims scope every read exactly as for staff.

Like notify(), these do not commit -- callers commit together with the
state change that triggered the notification.
"""
from app.notifications.services import notify


def _active_portal_user_ids(model, tenant_id, **owner_filter):
    rows = model.query.filter_by(tenant_id=tenant_id, is_active=True, **owner_filter).all()
    return [r.id for r in rows]


def notify_subcontractor_users(tenant_id, *, subcontractor_id, type, title, body=None, data=None):
    from app.modules.scp.models import SubcontractorPortalUser

    ids = _active_portal_user_ids(SubcontractorPortalUser, tenant_id, subcontractor_id=subcontractor_id)
    return [notify(tenant_id, user_id=uid, type=type, title=title, body=body, data=data) for uid in ids]


def notify_vendor_users(tenant_id, *, vendor_id, type, title, body=None, data=None):
    from app.modules.vnp.models import VendorPortalUser

    ids = _active_portal_user_ids(VendorPortalUser, tenant_id, vendor_id=vendor_id)
    return [notify(tenant_id, user_id=uid, type=type, title=title, body=body, data=data) for uid in ids]


def email_vendor_users(tenant_id, *, vendor_id, subject, body):
    """Queue a plain email to every active user of a vendor organisation.
    Portal users have no staff `users` row, so notify()'s email channel
    cannot reach them; this sends to the address on the portal account.
    Never raises: a missing mail setup must not fail the caller's request."""
    import logging

    from app.modules.vnp.models import VendorPortalUser
    from app.notifications.tasks import send_email_notification

    rows = VendorPortalUser.query.filter_by(tenant_id=tenant_id, vendor_id=vendor_id, is_active=True).all()
    for row in rows:
        if not row.email:
            continue
        try:
            send_email_notification.delay(to_address=row.email, subject=subject, body=body)
        except Exception:
            logging.getLogger(__name__).exception("Could not queue RFQ invitation email")
