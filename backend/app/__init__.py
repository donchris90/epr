"""
SiteForge backend application factory.

Modular monolith: a single deployable Flask app internally organized into
25 bounded-context modules (see app/modules/*), each owning its own tables
and exposing a Python service interface (SRS Section 3.3).
"""
import click
import os
from flask import Flask

from app.config import get_config
from app.extensions import db, migrate, jwt, cors, celery, configure_celery, cache, limiter
from app.middleware.tenant_context import register_tenant_context


# Every module's blueprint, in the order listed in SRS Section 4.
MODULE_BLUEPRINTS = [
    ("app.modules.bdc.routes", "bp"),
    ("app.modules.tbm.routes", "bp"),
    ("app.modules.est.routes", "bp"),
    ("app.modules.ctm.routes", "bp"),
    ("app.modules.pln.routes", "bp"),
    ("app.modules.exe.routes", "bp"),
    ("app.modules.prc.routes", "bp"),
    ("app.modules.inv.routes", "bp"),
    ("app.modules.eqp.routes", "bp"),
    ("app.modules.fuel.routes", "bp"),
    ("app.modules.wfm.routes", "bp"),
    ("app.modules.sub.routes", "bp"),
    ("app.modules.qms.routes", "bp"),
    ("app.modules.hse.routes", "bp"),
    ("app.modules.svy.routes", "bp"),
    ("app.modules.pq.routes", "bp"),
    ("app.modules.fin.routes", "bp"),
    ("app.modules.bil.routes", "bp"),
    ("app.modules.pc.routes", "bp"),
    ("app.modules.ast.routes", "bp"),
    ("app.modules.exd.routes", "bp"),
    ("app.modules.clp.routes", "bp"),
    ("app.modules.vnp.routes", "bp"),
    ("app.modules.scp.routes", "bp"),
    ("app.modules.mfa.routes", "bp"),
    ("app.modules.ai.routes", "bp"),
]


def create_app(config_name: str = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    # Real startup validation, added after a real production incident:
    # an invitation email went out with a working http://localhost:5173
    # link instead of the real deployed frontend, because FRONTEND_URL
    # was never actually set on Render -- silently falling back to the
    # local-dev default (app/config.py) with no warning anywhere. This
    # can't auto-fix a missing env var, but it makes the misconfiguration
    # immediately visible in the deploy logs the moment it happens again,
    # rather than only discovered when someone reports a broken link.
    effective_env = config_name or os.environ.get("FLASK_ENV", "development")
    if effective_env == "production" and app.config["FRONTEND_URL"] == "http://localhost:5173":
        app.logger.warning(
            "FRONTEND_URL is not set (or still the local-dev default) in a production "
            "environment -- invitation links and other user-facing URLs will point at "
            "localhost, not the real deployed frontend. Set FRONTEND_URL to the real "
            "frontend origin (e.g. https://siteforge-web.onrender.com) in this service's "
            "environment variables."
        )

    # --- error tracking (SRS Section 6) ---
    # Previously in requirements.txt but sentry_sdk.init() was never
    # actually called anywhere in this codebase -- a production outage
    # would have been invisible until a user complained. Only runs
    # when SENTRY_DSN is actually configured, so local dev and tests
    # (which leave it unset) never try to report anywhere.
    if app.config.get("SENTRY_DSN"):
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration

        sentry_sdk.init(
            dsn=app.config["SENTRY_DSN"],
            integrations=[FlaskIntegration()],
            traces_sample_rate=0.1,
            environment=config_name or "production",
        )

    # --- extensions ---
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, supports_credentials=True, origins=app.config["CORS_ORIGINS"])
    cache.init_app(app)
    # Real fix for a real bug: previously only app/celery_app.py (the
    # separate worker script) ever configured this -- the actual web
    # service never did, so every .delay() call made from within a
    # live request queued against Celery's unconfigured default
    # broker, completely disconnected from the real Redis broker (and
    # from CELERY_TASK_ALWAYS_EAGER, for deployments with no worker
    # process running at all). See configure_celery's own docstring.
    configure_celery(app)

    # --- metrics (SRS Section 6) ---
    # Same story as Sentry above: configured in requirements.txt,
    # never actually wired up. Exposes real request-count/latency
    # metrics at GET /metrics for a Prometheus scraper -- skipped
    # during tests (TESTING=True) since it registers a route on every
    # app instance the test suite creates, which is unnecessary noise
    # for ~500 test-app constructions across the suite.
    if not app.config.get("TESTING"):
        from prometheus_flask_exporter import PrometheusMetrics

        PrometheusMetrics(app)

    # RATELIMIT_STORAGE_URI must be set BEFORE limiter.init_app(app) --
    # Flask-Limiter reads it during initialization, not lazily.
    app.config.setdefault("RATELIMIT_STORAGE_URI", app.config["REDIS_URL"])
    limiter.init_app(app)

    # A revoked refresh token (via POST /v1/auth/logout) must actually
    # be rejected on its next use, not just recorded -- this callback
    # is what makes app/auth/jwt_utils.py's Redis-backed revocation
    # check run on every token verification, access or refresh alike.
    @jwt.token_in_blocklist_loader
    def _check_if_token_revoked(jwt_header, jwt_payload):
        from app.auth.jwt_utils import is_token_revoked

        return is_token_revoked(jwt_payload["jti"])

    # --- tenant-context middleware (SRS Section 3.4 / 5.5) ---
    register_tenant_context(app, db)

    # --- auth blueprint ---
    from app.auth.routes import bp as auth_bp
    app.register_blueprint(auth_bp)

    # --- document storage blueprint (cross-cutting infrastructure, SRS 5.2) ---
    from app.documents.routes import bp as documents_bp
    app.register_blueprint(documents_bp)

    # --- tenant onboarding blueprint (genuinely public, no tenant context yet) ---
    from app.onboarding.routes import bp as onboarding_bp
    app.register_blueprint(onboarding_bp)

    # --- DSAR search blueprint (SRS Section 6 / data-protection tooling) ---
    from app.dsar.routes import bp as dsar_bp
    app.register_blueprint(dsar_bp)

    # --- Workflow Engine (Module 26, generic cross-module approval engine) ---
    from app.workflow.routes import bp as workflow_bp
    app.register_blueprint(workflow_bp)

    # --- Cross-cutting Project listing (replaces raw UUID-paste fields) ---
    from app.projects.routes import bp as projects_bp
    app.register_blueprint(projects_bp)

    # --- Global search ---
    from app.search.routes import bp as search_bp
    app.register_blueprint(search_bp)

    # --- Subscription billing (monthly/annual plans, 14-day trial) ---
    from app.billing.routes import bp as billing_bp
    app.register_blueprint(billing_bp)

    # --- Organization user management (invitations, seats, roles) ---
    from app.org.routes import bp as org_bp
    app.register_blueprint(org_bp)

    # --- Platform administration (cross-tenant, separate credential type) ---
    from app.platform_admin.routes import bp as platform_admin_bp
    app.register_blueprint(platform_admin_bp)

    # --- Notifications (in-app + real email dispatch via Gmail SMTP; SMS not implemented by choice) ---
    from app.notifications.routes import bp as notifications_bp
    app.register_blueprint(notifications_bp)

    # --- Commitment accounting (read-only, computed from PRC data) ---
    from app.commitments.routes import bp as commitments_bp
    app.register_blueprint(commitments_bp)

    # --- module blueprints ---
    import importlib

    for module_path, attr in MODULE_BLUEPRINTS:
        module = importlib.import_module(module_path)
        app.register_blueprint(getattr(module, attr))

    # --- error handlers (RFC 7807 Problem Details, SRS Section 6.1) ---
    from app.utils.errors import register_error_handlers
    register_error_handlers(app)

    # --- security headers (SRS Section 6) ---
    # Previously entirely absent -- every response left the app bare.
    # This is a JSON API consumed by a separate SPA (not server-rendered
    # HTML), so a strict CSP limiting script/style sources isn't the
    # relevant control here the way it would be for an HTML-serving
    # app; what matters for an API are the headers that stop a browser
    # from doing something unsafe with a JSON response it was tricked
    # into loading somewhere it shouldn't be.
    @app.after_request
    def _set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # HSTS only makes sense once the app is actually served over
        # HTTPS -- forcing it in local dev (plain http://localhost)
        # would make browsers refuse to load the app at all.
        if not app.config.get("TESTING") and not app.config.get("DEBUG"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    @app.get("/v1/health")
    @limiter.exempt
    def platform_health():
        return {"status": "ok", "service": "siteforge-api"}

    @app.cli.command("create-platform-admin")
    @click.option("--email", required=True, help="Platform admin email")
    def create_platform_admin_command(email):
        """Bootstrap a real platform admin account -- prompts for the
        password interactively (never a plain-text CLI argument or a
        migration-embedded value; see migrations/versions/0039_platform_admin.py's
        own note on exactly why)."""
        import getpass

        from app.platform_admin.services import create_platform_admin

        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            click.echo("Passwords do not match.")
            return
        if len(password) < 8:
            click.echo("Password must be at least 8 characters.")
            return

        admin = create_platform_admin(email, password)
        click.echo(f"Created platform admin: {admin.email} ({admin.id})")

    return app
