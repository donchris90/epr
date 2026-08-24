"""
Notifications. Base path: /v1/notifications

Deliberately no @require_permission on any route here -- unlike every
other module's routes, which gate a business action behind an RBAC
permission, these routes only ever return or act on the calling user's
own notifications (every query is scoped by g.user_id, not something
a permission grant would broaden or narrow). Being authenticated at
all -- already enforced by the tenant-context middleware before any
route in this app is reached -- is the only real access requirement
for "can I see my own notification bell."
"""
from flask import Blueprint, g, jsonify, request

from app.notifications import services
from app.notifications.models import Notification
from app.notifications.schemas import NotificationSchema
from app.utils.errors import APIError
from app.utils.pagination import envelope

bp = Blueprint("notifications", __name__, url_prefix="/v1/notifications")

notification_schema = NotificationSchema()


def _get_notification_or_404(notification_id) -> Notification:
    n = Notification.query.filter_by(id=notification_id, tenant_id=g.tenant_id, user_id=g.user_id).first()
    if not n:
        raise APIError("Notification not found", status=404)
    return n


@bp.get("")
def list_notifications():
    unread_only = request.args.get("unread_only", "false").lower() == "true"
    limit = min(int(request.args.get("limit", 50)), 200)
    items = services.list_for_user(g.tenant_id, user_id=g.user_id, unread_only=unread_only, limit=limit)
    return jsonify(envelope(notification_schema.dump(items, many=True)))


@bp.get("/unread-count")
def unread_count():
    return jsonify({"unread_count": services.count_unread(g.tenant_id, user_id=g.user_id)})


@bp.post("/<uuid:notification_id>/read")
def mark_read(notification_id):
    notification = _get_notification_or_404(notification_id)
    notification = services.mark_read(notification)
    return jsonify(notification_schema.dump(notification))


@bp.post("/<uuid:notification_id>/unread")
def mark_unread(notification_id):
    notification = _get_notification_or_404(notification_id)
    notification = services.mark_unread(notification)
    return jsonify(notification_schema.dump(notification))


@bp.post("/mark-all-read")
def mark_all_read():
    services.mark_all_read(g.tenant_id, user_id=g.user_id)
    return jsonify({"status": "ok"})
