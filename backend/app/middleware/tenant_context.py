"""
Tenant Context Middleware (SRS Section 3.4 / 5.5).

Resolves tenant_id from the verified JWT and sets it as a Postgres
session variable (`app.tenant_id`) at the start of every request, so
Row-Level Security policies on every tenant-scoped table can enforce
isolation at the database layer — a bug in application-layer filtering
cannot leak cross-tenant data, because the database itself refuses to
return rows outside the current tenant.

This is the single most safety-critical file in the platform. Every
tenant-scoped table's RLS policy depends on this variable being set
correctly, and reset between requests.

IMPORTANT -- why this uses an `after_begin` ORM event and not just a
one-shot `SET LOCAL` in `before_request`:

`SET LOCAL` is scoped to a single Postgres transaction. A single Flask
request routinely spans *multiple* transactions -- every
`db.session.commit()` inside a service function ends one transaction,
and Flask-SQLAlchemy's default `expire_on_commit=True` means the very
next attribute access on a committed object (e.g. serializing it in the
response) silently opens a new one. A `SET LOCAL` issued only in
`before_request` would therefore apply to the *first* transaction only;
every later transaction in the same request would fall back to
Postgres's empty-string placeholder for an unset custom GUC, and every
RLS policy would then evaluate `tenant_id = ''::uuid`, which errors.

The fix: register a SQLAlchemy `after_begin` event that re-issues
`SET LOCAL app.tenant_id = ...` at the start of *every* transaction for
the lifetime of the request, not just the first.
"""
from flask import g, has_request_context, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt
from sqlalchemy import event, text
from sqlalchemy.orm import Session


# Paths this middleware's own before_request skips entirely. Two
# different reasons land a path here:
#   - /v1/health and /v1/auth/login genuinely take no JWT at all.
#   - /v1/auth/refresh and /v1/auth/logout DO require a valid JWT, but
#     specifically a *refresh* token, which the route's own
#     @jwt_required(refresh=True) decorator correctly verifies. This
#     middleware's verify_jwt_in_request(optional=True) call below
#     defaults to expecting an *access* token; without this exemption,
#     it would reject a valid refresh token before the route ever runs
#     ("Only non-refresh tokens are allowed") -- which is exactly what
#     happened to /logout until this was added, since only /refresh
#     was originally exempted here despite both routes needing it.
PUBLIC_PATHS = {
    "/v1/health",
    "/v1/auth/login",
    # Genuinely public -- a person requesting a reset, or completing
    # one via an emailed link, has no session/JWT at all yet, the same
    # real reason /v1/auth/login itself is exempt.
    "/v1/auth/forgot-password",
    "/v1/auth/reset-password",
    "/v1/auth/refresh",
    "/v1/auth/logout",
    "/v1/onboarding/signup",
    "/v1/platform-admin/auth/login",
    "/v1/billing/paystack/webhook",
    "/v1/org/invitations/preview",
    "/v1/org/invitations/accept",
    # Client Portal's own login family (client-facing portal build) --
    # same two reasons as the /v1/auth/* entries above: /login takes no
    # JWT at all, /refresh and /logout take a refresh token specifically,
    # which this middleware's own optional access-token check would
    # otherwise reject before either route's @jwt_required(refresh=True)
    # ever ran.
    "/v1/clp/auth/login",
    "/v1/clp/auth/refresh",
    "/v1/clp/auth/logout",
    # Subcontractor Portal (SCP) and Vendor Portal (VNP) -- same real
    # reasoning as CLP's own auth family above: no session/JWT exists
    # yet at login, or the token being used is a refresh/logout token
    # rather than an access token.
    "/v1/scp/auth/login",
    "/v1/scp/auth/refresh",
    "/v1/scp/auth/logout",
    "/v1/vnp/auth/login",
    "/v1/vnp/auth/refresh",
    "/v1/vnp/auth/logout",
}

# Paths a tenant must still be able to reach even when its
# subscription isn't active -- otherwise a tenant that just went
# inactive could never see its own billing page or plans to actually
# fix that. Checked as a prefix, not exact match, since this covers
# every route under the billing blueprint.
SUBSCRIPTION_EXEMPT_PREFIXES = ("/v1/billing",)


def register_tenant_context(app, db):
    @app.before_request
    def set_tenant_context():
        # CORS preflight (OPTIONS) requests never carry an Authorization
        # header -- that's normal browser behavior, not a client bug --
        # and never reach real view logic regardless. Found in
        # production, not in this suite's own tests: calling get_jwt()
        # after verify_jwt_in_request(optional=True) crashes
        # specifically for OPTIONS (a plain unauthenticated GET to the
        # same path correctly returns a clean 403; OPTIONS raised
        # instead), which surfaced as a 500 on every CORS preflight to
        # any protected route -- i.e. the entire frontend, cross-origin,
        # for every request. Skipping OPTIONS here entirely is the
        # correct fix regardless of that internal nuance: this
        # middleware has no business running on a request that never
        # reaches a route handler in the first place.
        if request.method == "OPTIONS":
            return

        if request.path in PUBLIC_PATHS or request.path.endswith("/health"):
            return

        # Verify JWT and extract tenant_id claim (optional=True lets
        # individual routes decide whether auth is required).
        verify_jwt_in_request(optional=True)
        claims = get_jwt() or {}
        tenant_id = claims.get("tenant_id")
        g.tenant_id = tenant_id
        g.user_id = claims.get("user_id")
        g.role_id = claims.get("role_id")
        g.permissions = claims.get("permissions", [])
        # Client Portal build: distinguishes a client-facing session
        # (issued only by /v1/clp/auth/login) from an internal staff
        # session, so routes that must never let a client act as
        # another client (see app/modules/clp/routes.py's own
        # _get_client_user_or_404) can tell the two apart. Absent
        # entirely from every staff-issued token, so `g.get("is_client")`
        # is falsy for all pre-existing sessions with no change needed
        # anywhere else.
        g.is_client = claims.get("is_client", False)
        # Subcontractor Portal (SCP) and Vendor Portal (VNP) build:
        # same real reasoning as is_client above, one shared claim
        # name since both portals' user_id values are equally "not the
        # staff User table" from this check's perspective -- a
        # SubcontractorPortalUser.id and a VendorPortalUser.id are
        # different models from each other too, but neither has a
        # pwd_ts mechanism of its own yet (see
        # docs/SUBCONTRACTOR_VENDOR_PORTAL_GAPS.md), so skipping the
        # check entirely for either is correct today, not just safe.
        g.is_portal_user = claims.get("is_portal_user", False)

        # Real session-invalidation check, added alongside password
        # reset support -- staff sessions only (this codebase's
        # separate client/subcontractor/vendor portal password changes
        # have no equivalent mechanism yet and aren't this check's
        # scope; those portals' user_id values refer to different
        # models entirely, so running this same check against them
        # would be checking the wrong table). A token whose pwd_ts
        # claim no longer matches the user's real, current
        # password_changed_at was issued before their most recent
        # password change and must stop working immediately, not just
        # expire naturally over the next 30 days.
        if tenant_id and g.user_id and not g.is_client and not g.is_portal_user:
            from app.auth.jwt_utils import check_pwd_ts_claim

            if not check_pwd_ts_claim(tenant_id, g.user_id, claims.get("pwd_ts")):
                from app.utils.errors import APIError

                raise APIError("Session no longer valid", status=401)

        # Covers the transaction already open (if any) at the start of
        # this request; the after_begin listener below covers every
        # transaction opened after this point.
        if tenant_id:
            db.session.execute(
                text("SET LOCAL app.tenant_id = :tenant_id"),
                {"tenant_id": str(tenant_id)},
            )

            # Real enforcement, not cosmetic: a tenant whose trial has
            # lapsed with no active subscription gets a real 402 on
            # every route except billing itself (SUBSCRIPTION_EXEMPT_PREFIXES)
            # -- otherwise they could never reach the page that lets
            # them fix it. The frontend turns a 402 into a redirect to
            # a real subscription-expired page
            # (frontend/src/pages/SubscriptionExpiredPage.tsx), not
            # just a banner. Platform-admin requests carry no tenant_id
            # at all (see app/platform_admin/routes.py), so this
            # entire block is naturally skipped for them without a
            # separate exemption.
            if not request.path.startswith(SUBSCRIPTION_EXEMPT_PREFIXES):
                from app.billing.services import is_tenant_active

                if not is_tenant_active(tenant_id):
                    from flask import jsonify

                    response = jsonify({
                        "type": "about:blank",
                        "title": "Subscription required",
                        "status": 402,
                        "detail": "This tenant's trial or subscription has ended.",
                    })
                    response.status_code = 402
                    return response

    @event.listens_for(Session, "after_begin")
    def _set_tenant_on_new_transaction(session, transaction, connection):
        # Fires for every transaction (including ones implicitly opened
        # after a commit) on every Session for the app's lifetime, so it
        # must be cheap and must no-op outside of a tenant-bearing
        # request (e.g. background scripts, Celery tasks, migrations).
        if not has_request_context():
            return
        tenant_id = getattr(g, "tenant_id", None)
        if tenant_id:
            connection.execute(
                text("SET LOCAL app.tenant_id = :tenant_id"),
                {"tenant_id": str(tenant_id)},
            )

    @app.teardown_appcontext
    def clear_tenant_context(exception=None):
        # SET LOCAL is transaction-scoped and clears automatically on
        # commit/rollback, but we drop the Flask `g` reference too.
        g.pop("tenant_id", None)
        g.pop("user_id", None)
        g.pop("role_id", None)
        g.pop("permissions", None)
