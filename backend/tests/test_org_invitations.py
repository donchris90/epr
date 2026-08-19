"""
Tests for app/org/ -- real invitations, real seat-limit enforcement
against the tenant's actual subscription plan, and user management
actions. Mocks the real email dispatch (send_email_notification.delay)
throughout -- the same reasoning as mocking Paystack's HTTP call in
test_paystack_billing.py: this suite verifies application logic, not
that a live Celery broker/SMTP server is reachable in CI.
"""
from unittest.mock import patch

from sqlalchemy import text


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def _seed_plan_and_subscription(db, tenant_id, seat_limit):
    from app.billing.models import SubscriptionPlan, TenantSubscription

    _as_tenant(db, tenant_id)
    plan = SubscriptionPlan(code=f"_org_test_{seat_limit}", name="Test Plan", monthly_price_ngn=0, annual_price_ngn=0, seat_limit=seat_limit, is_active=False)
    db.session.add(plan)
    db.session.flush()
    # seed_tenants (conftest.py) already created a subscription row --
    # update it rather than inserting a conflicting second one.
    from app.billing.models import TenantSubscription

    sub = TenantSubscription.query.filter_by(tenant_id=tenant_id).first()
    sub.plan_id = plan.id
    sub.status = "active"
    db.session.commit()
    return plan


def _make_role(db, tenant_id, permissions=None):
    from app.models.core import Role

    _as_tenant(db, tenant_id)
    role = Role(tenant_id=tenant_id, name="Member", permission_set=permissions or ["org:read", "org:manage"])
    db.session.add(role)
    db.session.commit()
    return role


class TestNotificationFailureDoesNotBreakInvitation:
    """
    Real regression coverage for a real production bug: with
    CELERY_TASK_ALWAYS_EAGER on (this session's real fix for Render's
    missing free-tier worker service), the notification task's
    retry-on-failure logic raises synchronously right in the calling
    request -- and that exception was propagating all the way up
    through invitation creation, both crashing the request with a 500
    AND silently preventing the invitation from ever being committed
    (create_invitation flushes but doesn't commit before sending the
    email; the route commits afterward). Deliberately does NOT mock
    send_email_notification here -- the whole point is confirming the
    real, unmocked failure-and-retry path doesn't break anything.
    """

    def test_invitation_succeeds_even_when_email_dispatch_fails_in_eager_mode(self, app, db, client, seed_tenants, auth_headers):
        app.config["CELERY_TASK_ALWAYS_EAGER"] = True
        from app.extensions import configure_celery

        configure_celery(app)
        # SMTP deliberately left unconfigured (empty username/password,
        # the seed_tenants/app fixture default) -- send_email_notification
        # will genuinely fail and retry, exactly reproducing the real bug.
        app.config["SMTP_USERNAME"] = ""
        app.config["SMTP_PASSWORD"] = ""

        _seed_plan_and_subscription(db, seed_tenants["a"], seat_limit=10)
        role = _make_role(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["org:manage", "org:read"])

        r = client.post("/v1/org/invitations", headers=headers, json={"email": "eagerfail@example.com", "role_id": str(role.id)})

        assert r.status_code == 201
        assert r.get_json()["email"] == "eagerfail@example.com"

        # The real point: genuinely, durably committed, not silently
        # rolled back by the exception that used to propagate through here.
        _as_tenant(db, seed_tenants["a"])
        from app.org.models import Invitation

        saved = Invitation.query.filter_by(tenant_id=seed_tenants["a"], email="eagerfail@example.com").first()
        assert saved is not None
        assert saved.status == "pending"

        app.config["CELERY_TASK_ALWAYS_EAGER"] = False
        configure_celery(app)


@patch("app.org.services.send_email_notification")
class TestSeatLimitEnforcement:
    def test_can_invite_up_to_the_seat_limit(self, mock_email, app, db, client, seed_tenants, auth_headers):
        _seed_plan_and_subscription(db, seed_tenants["a"], seat_limit=2)
        role = _make_role(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["org:manage", "org:read"])

        # 1 seat already "used" by the fixture's own baseline (no real
        # user created by seed_tenants, so this tenant starts at 0
        # active users) -- invite up to the limit.
        r1 = client.post("/v1/org/invitations", headers=headers, json={"email": "u1@example.com", "role_id": str(role.id)})
        assert r1.status_code == 201
        r2 = client.post("/v1/org/invitations", headers=headers, json={"email": "u2@example.com", "role_id": str(role.id)})
        assert r2.status_code == 201

    def test_exceeding_the_seat_limit_is_rejected_with_402(self, mock_email, app, db, client, seed_tenants, auth_headers):
        _seed_plan_and_subscription(db, seed_tenants["a"], seat_limit=1)
        role = _make_role(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["org:manage", "org:read"])

        r1 = client.post("/v1/org/invitations", headers=headers, json={"email": "u1@example.com", "role_id": str(role.id)})
        assert r1.status_code == 201

        r2 = client.post("/v1/org/invitations", headers=headers, json={"email": "u2@example.com", "role_id": str(role.id)})
        assert r2.status_code == 402
        assert "limit" in r2.get_json()["title"].lower()

    def test_pending_invitations_count_toward_the_limit(self, mock_email, app, db, client, seed_tenants, auth_headers):
        """Phase 34's real policy: a pending invitation reserves a
        seat immediately, not only once accepted."""
        _seed_plan_and_subscription(db, seed_tenants["a"], seat_limit=1)
        role = _make_role(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["org:manage", "org:read"])

        client.post("/v1/org/invitations", headers=headers, json={"email": "u1@example.com", "role_id": str(role.id)})

        r = client.get("/v1/org/seats", headers=headers)
        assert r.get_json()["seats_used"] == 1
        assert r.get_json()["seats_remaining"] == 0

    def test_upgrading_the_plan_unblocks_further_invitations(self, mock_email, app, db, client, seed_tenants, auth_headers):
        """The exact Phase 57 scenario: hit the limit, upgrade,
        confirm the next invite succeeds."""
        _seed_plan_and_subscription(db, seed_tenants["a"], seat_limit=1)
        role = _make_role(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["org:manage", "org:read"])

        client.post("/v1/org/invitations", headers=headers, json={"email": "u1@example.com", "role_id": str(role.id)})
        r_blocked = client.post("/v1/org/invitations", headers=headers, json={"email": "u2@example.com", "role_id": str(role.id)})
        assert r_blocked.status_code == 402

        _seed_plan_and_subscription(db, seed_tenants["a"], seat_limit=20)

        r_after_upgrade = client.post("/v1/org/invitations", headers=headers, json={"email": "u2@example.com", "role_id": str(role.id)})
        assert r_after_upgrade.status_code == 201

    def test_unlimited_plan_never_blocks(self, mock_email, app, db, client, seed_tenants, auth_headers):
        _seed_plan_and_subscription(db, seed_tenants["a"], seat_limit=None)
        role = _make_role(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["org:manage", "org:read"])

        for i in range(5):
            r = client.post("/v1/org/invitations", headers=headers, json={"email": f"u{i}@example.com", "role_id": str(role.id)})
            assert r.status_code == 201


@patch("app.org.services.send_email_notification")
class TestInvitationManagement:
    def test_invitation_email_link_matches_the_real_frontend_route(self, mock_email, app, db, client, seed_tenants, auth_headers):
        """Real regression test: the email previously linked to
        /accept-invitation/{token} (token as a path segment), but the
        actual frontend route (frontend/src/App.tsx) has no path
        parameter there at all -- AcceptInvitationPage.tsx reads the
        token from a query string. A real invitee clicking that email
        link would have hit a dead route. Confirms the fix: the
        generated link uses ?token=, matching what the frontend page
        actually reads."""
        _seed_plan_and_subscription(db, seed_tenants["a"], seat_limit=10)
        role = _make_role(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["org:manage", "org:read"])

        client.post("/v1/org/invitations", headers=headers, json={"email": "linktest@example.com", "role_id": str(role.id)})

        body_kwargs = mock_email.delay.call_args.kwargs
        assert "/accept-invitation?token=" in body_kwargs["body"]
        assert "/accept-invitation/" not in body_kwargs["body"]

    def test_duplicate_pending_invitation_is_rejected(self, mock_email, app, db, client, seed_tenants, auth_headers):
        _seed_plan_and_subscription(db, seed_tenants["a"], seat_limit=10)
        role = _make_role(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["org:manage", "org:read"])

        client.post("/v1/org/invitations", headers=headers, json={"email": "dup@example.com", "role_id": str(role.id)})
        r = client.post("/v1/org/invitations", headers=headers, json={"email": "dup@example.com", "role_id": str(role.id)})
        assert r.status_code == 409

    def test_cancel_frees_the_seat(self, mock_email, app, db, client, seed_tenants, auth_headers):
        _seed_plan_and_subscription(db, seed_tenants["a"], seat_limit=1)
        role = _make_role(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["org:manage", "org:read"])

        r = client.post("/v1/org/invitations", headers=headers, json={"email": "u1@example.com", "role_id": str(role.id)})
        invitation_id = r.get_json()["id"]

        r_blocked = client.post("/v1/org/invitations", headers=headers, json={"email": "u2@example.com", "role_id": str(role.id)})
        assert r_blocked.status_code == 402

        r_cancel = client.post(f"/v1/org/invitations/{invitation_id}/cancel", headers=headers)
        assert r_cancel.status_code == 200

        r_now_allowed = client.post("/v1/org/invitations", headers=headers, json={"email": "u2@example.com", "role_id": str(role.id)})
        assert r_now_allowed.status_code == 201

    def test_resend_invalidates_the_old_token(self, mock_email, app, db, client, seed_tenants, auth_headers):
        from app.org import services

        _seed_plan_and_subscription(db, seed_tenants["a"], seat_limit=10)
        role = _make_role(db, seed_tenants["a"])
        _as_tenant(db, seed_tenants["a"])

        invitation = services.create_invitation(seed_tenants["a"], email="resend@example.com", role_id=role.id, invited_by_user_id=None)
        # Captured as plain values before commit, not accessed on the
        # ORM object afterward -- expire_on_commit means any later
        # attribute access can trigger a fresh SELECT needing tenant
        # context that isn't set at that point in this test.
        invitation_id = str(invitation.id)
        old_hash = invitation.token_hash
        db.session.commit()

        headers = auth_headers("a", permissions=["org:manage", "org:read"])
        r = client.post(f"/v1/org/invitations/{invitation_id}/resend", headers=headers)
        assert r.status_code == 200

        _as_tenant(db, seed_tenants["a"])
        from app.org.models import Invitation

        refreshed = Invitation.query.filter_by(id=invitation_id).first()
        assert refreshed.token_hash != old_hash


@patch("app.org.services.send_email_notification")
class TestAcceptInvitationFlow:
    def test_full_accept_flow_creates_a_real_login_capable_user(self, mock_email, app, db, client, seed_tenants):
        from app.org import services

        _seed_plan_and_subscription(db, seed_tenants["a"], seat_limit=10)
        role = _make_role(db, seed_tenants["a"])
        _as_tenant(db, seed_tenants["a"])

        with patch("app.org.services.secrets.token_urlsafe", return_value="fixed-test-token-abc123"):
            invitation = services.create_invitation(seed_tenants["a"], email="newuser@example.com", role_id=role.id, invited_by_user_id=None)
        db.session.commit()

        r_preview = client.get("/v1/org/invitations/preview?token=fixed-test-token-abc123")
        assert r_preview.status_code == 200
        assert r_preview.get_json()["email"] == "newuser@example.com"

        r_accept = client.post("/v1/org/invitations/accept", json={"token": "fixed-test-token-abc123", "password": "newpassword123"})
        assert r_accept.status_code == 201
        assert "access_token" in r_accept.get_json()

        r_login = client.post("/v1/auth/login", json={"email": "newuser@example.com", "password": "newpassword123"})
        assert r_login.status_code == 200

    def test_used_token_cannot_be_reused(self, mock_email, app, db, client, seed_tenants):
        from app.org import services

        _seed_plan_and_subscription(db, seed_tenants["a"], seat_limit=10)
        role = _make_role(db, seed_tenants["a"])
        _as_tenant(db, seed_tenants["a"])

        with patch("app.org.services.secrets.token_urlsafe", return_value="single-use-token-xyz"):
            services.create_invitation(seed_tenants["a"], email="singleuse@example.com", role_id=role.id, invited_by_user_id=None)
        db.session.commit()

        r1 = client.post("/v1/org/invitations/accept", json={"token": "single-use-token-xyz", "password": "password123"})
        assert r1.status_code == 201

        r2 = client.post("/v1/org/invitations/accept", json={"token": "single-use-token-xyz", "password": "differentpass123"})
        assert r2.status_code == 400

    def test_expired_invitation_cannot_be_accepted(self, mock_email, app, db, seed_tenants, client):
        from app.org import services
        from app.org.models import Invitation
        from datetime import datetime, timedelta, timezone

        _seed_plan_and_subscription(db, seed_tenants["a"], seat_limit=10)
        role = _make_role(db, seed_tenants["a"])
        _as_tenant(db, seed_tenants["a"])

        with patch("app.org.services.secrets.token_urlsafe", return_value="expired-token-123"):
            invitation = services.create_invitation(seed_tenants["a"], email="expired@example.com", role_id=role.id, invited_by_user_id=None)
        invitation.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.session.commit()

        r = client.post("/v1/org/invitations/accept", json={"token": "expired-token-123", "password": "password123"})
        assert r.status_code == 400

    def test_invalid_token_returns_a_clean_400_not_a_500(self, mock_email, app, db, client, seed_tenants):
        r = client.post("/v1/org/invitations/accept", json={"token": "totally-made-up-token", "password": "password123"})
        assert r.status_code == 400


class TestListRoles:
    def test_lists_the_tenants_real_dynamic_roles(self, app, db, client, seed_tenants, auth_headers):
        _make_role(db, seed_tenants["a"])
        headers = auth_headers("a", permissions=["org:read"])

        r = client.get("/v1/org/roles", headers=headers)
        assert r.status_code == 200
        names = {role["name"] for role in r.get_json()["data"]}
        assert "Member" in names

    def test_cross_tenant_isolation(self, app, db, client, seed_tenants, auth_headers):
        _make_role(db, seed_tenants["a"])
        headers_b = auth_headers("b", permissions=["org:read"])

        r = client.get("/v1/org/roles", headers=headers_b)
        assert r.status_code == 200
        assert r.get_json()["data"] == []


class TestUserManagementActions:
    def test_suspend_blocks_login_and_reactivate_restores_it(self, app, db, client, seed_tenants, auth_headers):
        from app.models.core import User
        from app.auth.jwt_utils import hash_password
        from app.models.core import EmailTenantIndex

        role = _make_role(db, seed_tenants["a"])
        _as_tenant(db, seed_tenants["a"])
        user = User(tenant_id=seed_tenants["a"], email="suspendable@example.com", password_hash=hash_password("password123"), role_id=role.id, status="active")
        db.session.add(user)
        db.session.flush()
        db.session.add(EmailTenantIndex(email=user.email, user_id=user.id, tenant_id=seed_tenants["a"]))
        db.session.commit()

        admin_headers = auth_headers("a", permissions=["org:manage", "org:read"])

        r_before = client.post("/v1/auth/login", json={"email": "suspendable@example.com", "password": "password123"})
        assert r_before.status_code == 200

        r_suspend = client.post(f"/v1/org/users/{user.id}/suspend", headers=admin_headers)
        assert r_suspend.status_code == 200

        r_blocked = client.post("/v1/auth/login", json={"email": "suspendable@example.com", "password": "password123"})
        assert r_blocked.status_code == 401

        r_reactivate = client.post(f"/v1/org/users/{user.id}/reactivate", headers=admin_headers)
        assert r_reactivate.status_code == 200

        r_restored = client.post("/v1/auth/login", json={"email": "suspendable@example.com", "password": "password123"})
        assert r_restored.status_code == 200

    def test_removed_users_are_excluded_from_the_member_list(self, app, db, client, seed_tenants, auth_headers):
        from app.models.core import User
        from app.auth.jwt_utils import hash_password

        role = _make_role(db, seed_tenants["a"])
        _as_tenant(db, seed_tenants["a"])
        user = User(tenant_id=seed_tenants["a"], email="removable@example.com", password_hash=hash_password("password123"), role_id=role.id, status="active")
        db.session.add(user)
        db.session.commit()

        admin_headers = auth_headers("a", permissions=["org:manage", "org:read"])
        client.post(f"/v1/org/users/{user.id}/remove", headers=admin_headers)

        r = client.get("/v1/org/members", headers=admin_headers)
        emails = [u["email"] for u in r.get_json()["users"]]
        assert "removable@example.com" not in emails

    def test_cross_tenant_isolation_on_members_list(self, app, db, client, seed_tenants, auth_headers):
        from app.models.core import User
        from app.auth.jwt_utils import hash_password

        role_a = _make_role(db, seed_tenants["a"])
        _as_tenant(db, seed_tenants["a"])
        db.session.add(User(tenant_id=seed_tenants["a"], email="tenant-a-user@example.com", password_hash=hash_password("x"), role_id=role_a.id, status="active"))
        db.session.commit()

        headers_b = auth_headers("b", permissions=["org:read"])
        r = client.get("/v1/org/members", headers=headers_b)
        emails = [u["email"] for u in r.get_json()["users"]]
        assert "tenant-a-user@example.com" not in emails
