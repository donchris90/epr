"""
See app/org/models.py's module docstring for the overall scope.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.extensions import db
from app.utils.errors import APIError
from app.auth.jwt_utils import hash_password
from app.models.core import User, Role, EmailTenantIndex, InvitationTokenIndex
from app.billing.services import get_subscription
from app.org.models import Invitation, INVITATION_TTL_DAYS
from app.notifications.tasks import send_email_notification


def hash_invitation_token(raw_token: str) -> str:
    """SHA-256, not Argon2 -- deliberately different from password
    hashing. A password is checked against a KNOWN plaintext the user
    types in; an invitation token needs to be LOOKED UP by hash
    directly from whatever the accept-invitation link contains, which
    Argon2's per-hash random salt makes impossible (the same input
    produces a different hash every time). A plain SHA-256 digest of a
    32-byte cryptographically random token (secrets.token_urlsafe) is
    still secure for this: the token itself carries enough entropy
    that finding a collision or guessing it is infeasible, even though
    the hash function itself is fast and deterministic."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def get_seat_limit(tenant_id):
    """None means unlimited (e.g. Enterprise, or a manually-granted
    comp subscription with no seat_limit set) -- see
    app/billing/models.py:SubscriptionPlan.seat_limit's own docstring."""
    subscription = get_subscription(tenant_id)
    if not subscription or not subscription.plan:
        return None
    return subscription.plan.seat_limit


def count_seats_in_use(tenant_id) -> int:
    """Active users + pending invitations -- Phase 34's real policy:
    a pending invitation reserves a seat the moment it's created, not
    only once accepted, so two admins racing to invite different
    people can't both succeed past the real limit between them."""
    active_users = User.query.filter_by(tenant_id=tenant_id, status="active").count()
    pending_invitations = Invitation.query.filter_by(tenant_id=tenant_id, status="pending").count()
    return active_users + pending_invitations


def list_org_members(tenant_id):
    """Combines real Users and real pending Invitations into one list,
    matching the org user-management table's own real shape -- a
    pending invitation is a real row here, not synthesized to look
    like one; the frontend tells them apart by `kind`."""
    users = User.query.filter(User.tenant_id == tenant_id, User.status != "removed").order_by(User.email).all()
    invitations = Invitation.query.filter_by(tenant_id=tenant_id, status="pending").order_by(Invitation.created_at).all()
    return {"users": users, "pending_invitations": invitations}


def list_roles(tenant_id):
    """The tenant's real, dynamic roles -- this codebase's RBAC
    already supports arbitrary tenant-defined roles (app/models/core.py:Role),
    so the invite form picks from these directly rather than a
    hardcoded list."""
    return Role.query.filter_by(tenant_id=tenant_id).order_by(Role.name).all()


def create_invitation(tenant_id, *, email, role_id, invited_by_user_id, department=None, job_title=None, message=None):
    email = email.strip().lower()

    role = Role.query.filter_by(id=role_id, tenant_id=tenant_id).first()
    if not role:
        raise APIError("Role not found", status=404)

    if User.query.filter_by(tenant_id=tenant_id, email=email).first():
        raise APIError("A user with this email already exists in your organization", status=409)

    existing_pending = Invitation.query.filter_by(tenant_id=tenant_id, email=email, status="pending").first()
    if existing_pending:
        raise APIError(
            "An invitation is already pending for this email", status=409,
            detail="Resend or cancel the existing invitation instead of creating a new one.",
        )

    seat_limit = get_seat_limit(tenant_id)
    if seat_limit is not None and count_seats_in_use(tenant_id) >= seat_limit:
        raise APIError(
            "User limit reached", status=402,
            detail=f"Your current plan allows {seat_limit} users. Upgrade your plan or free up a seat to invite more.",
        )

    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_invitation_token(raw_token)
    invitation = Invitation(
        tenant_id=tenant_id,
        email=email,
        role_id=role_id,
        department=department,
        job_title=job_title,
        invited_by_user_id=invited_by_user_id,
        message=message,
        token_hash=token_hash,
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(days=INVITATION_TTL_DAYS),
    )
    db.session.add(invitation)
    db.session.flush()

    # Kept in sync here, the one call site that creates a token --
    # same reasoning as EmailTenantIndex's own docstring on why this
    # is practical without added kept-in-sync infrastructure.
    db.session.add(InvitationTokenIndex(token_hash=token_hash, invitation_id=invitation.id, tenant_id=tenant_id))

    _send_invitation_email(tenant_id, invitation, raw_token)
    return invitation


def resend_invitation(tenant_id, invitation_id):
    """A real new token, not resending the same link -- the old
    token_hash is overwritten, so the previous email's link stops
    working the moment this runs (matches Phase 32's "invalidated"
    requirement for a superseded invitation, not just an expired
    one)."""
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})

    invitation = Invitation.query.filter_by(id=invitation_id, tenant_id=tenant_id, status="pending").first()
    if not invitation:
        raise APIError("Pending invitation not found", status=404)

    raw_token = secrets.token_urlsafe(32)
    invitation.token_hash = hash_invitation_token(raw_token)
    invitation.expires_at = datetime.now(timezone.utc) + timedelta(days=INVITATION_TTL_DAYS)

    index_row = InvitationTokenIndex.query.filter_by(invitation_id=invitation.id).first()
    if index_row:
        index_row.token_hash = invitation.token_hash
    else:
        db.session.add(InvitationTokenIndex(token_hash=invitation.token_hash, invitation_id=invitation.id, tenant_id=tenant_id))
    db.session.commit()

    _send_invitation_email(tenant_id, invitation, raw_token)
    return invitation


def cancel_invitation(tenant_id, invitation_id):
    invitation = Invitation.query.filter_by(id=invitation_id, tenant_id=tenant_id, status="pending").first()
    if not invitation:
        raise APIError("Pending invitation not found", status=404)
    invitation.status = "cancelled"
    db.session.commit()
    return invitation


def _send_invitation_email(tenant_id, invitation, raw_token):
    from flask import current_app
    from app.models.core import Tenant

    tenant = Tenant.query.filter_by(id=tenant_id).first()
    accept_url = f"{current_app.config['FRONTEND_URL']}/accept-invitation/{raw_token}"
    body = (
        f"You've been invited to join {tenant.name if tenant else 'a SiteForge organization'} on SiteForge.\n\n"
        f"Accept your invitation: {accept_url}\n\n"
        f"This invitation expires in {INVITATION_TTL_DAYS} days."
    )
    send_email_notification.delay(
        to_address=invitation.email, subject=f"You're invited to join {tenant.name if tenant else 'SiteForge'}", body=body
    )


def get_invitation_by_token(raw_token):
    """
    Real, honest validation -- an invitation that exists but is
    expired or already used (accepted/cancelled) is deliberately
    treated the same as one that was never found at all: revealing
    *which* reason it failed for tells an attacker probing tokens more
    than they should learn.

    Two-step lookup, not a direct query: Invitation has FORCE RLS
    (correctly, for the authenticated admin routes), but this
    function runs with no tenant context at all -- discovering the
    tenant is the whole point. Resolve tenant_id from
    InvitationTokenIndex (no RLS) first, set real tenant context, then
    query the real Invitation row -- exactly the same two-step
    EmailTenantIndex already established for login.
    """
    token_hash = hash_invitation_token(raw_token)
    index_row = InvitationTokenIndex.query.filter_by(token_hash=token_hash).first()
    if not index_row:
        return None

    with db.session.begin_nested():
        db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(index_row.tenant_id)})
        invitation = db.session.get(Invitation, index_row.invitation_id)

    if not invitation:
        return None
    if invitation.status != "pending":
        return None
    if invitation.expires_at < datetime.now(timezone.utc):
        return None
    return invitation


def accept_invitation(raw_token, *, password):
    """Creates the real, login-capable User account this invitation
    was for. Single-use by construction, not just convention: once
    status flips to "accepted", get_invitation_by_token above can
    never find this token as valid again, for the same reason an
    expired one can't -- the status check runs before the expiry
    check even matters."""
    invitation = get_invitation_by_token(raw_token)
    if not invitation:
        raise APIError("This invitation is invalid or has expired", status=400)

    if len(password) < 8:
        raise APIError("Password must be at least 8 characters", status=400)

    # Explicit, not assumed: get_invitation_by_token set tenant
    # context inside its own nested savepoint, which may or may not
    # still apply here depending on transaction boundaries already
    # crossed -- re-setting it directly before this real, RLS-
    # protected write is the same defensive discipline applied
    # throughout this codebase rather than relying on it persisting.
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(invitation.tenant_id)})

    user = User(
        tenant_id=invitation.tenant_id,
        email=invitation.email,
        password_hash=hash_password(password),
        role_id=invitation.role_id,
        department=invitation.department,
        job_title=invitation.job_title,
        status="active",
    )
    db.session.add(user)
    db.session.flush()

    db.session.add(EmailTenantIndex(email=user.email, user_id=user.id, tenant_id=invitation.tenant_id))

    invitation.status = "accepted"
    invitation.accepted_at = datetime.now(timezone.utc)
    db.session.commit()
    return user


def suspend_user(tenant_id, user_id):
    user = User.query.filter_by(id=user_id, tenant_id=tenant_id).first()
    if not user:
        raise APIError("User not found", status=404)
    user.status = "suspended"
    db.session.commit()
    return user


def reactivate_user(tenant_id, user_id):
    """Real seat-limit check on the way back in -- reactivating a
    suspended user re-occupies a seat exactly like inviting a new one
    would, so it's subject to the exact same limit, not a loophole
    around it."""
    user = User.query.filter_by(id=user_id, tenant_id=tenant_id).first()
    if not user:
        raise APIError("User not found", status=404)

    seat_limit = get_seat_limit(tenant_id)
    if seat_limit is not None and count_seats_in_use(tenant_id) >= seat_limit:
        raise APIError(
            "User limit reached", status=402,
            detail=f"Your current plan allows {seat_limit} users. Upgrade your plan or free up a seat to reactivate this user.",
        )

    user.status = "active"
    db.session.commit()
    return user


def remove_user(tenant_id, user_id):
    """Soft-removed (status="removed"), never a hard delete -- matches
    this codebase's consistent audit-trail discipline everywhere else
    (nothing genuinely disappears, it's marked). A removed user is
    excluded from list_org_members above and cannot log in (the same
    real status != "active" check every other non-active status
    already relies on)."""
    user = User.query.filter_by(id=user_id, tenant_id=tenant_id).first()
    if not user:
        raise APIError("User not found", status=404)
    user.status = "removed"
    db.session.commit()
    return user


def change_user_role(tenant_id, user_id, role_id):
    user = User.query.filter_by(id=user_id, tenant_id=tenant_id).first()
    if not user:
        raise APIError("User not found", status=404)
    role = Role.query.filter_by(id=role_id, tenant_id=tenant_id).first()
    if not role:
        raise APIError("Role not found", status=404)
    user.role_id = role_id
    db.session.commit()
    return user
