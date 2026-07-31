import os
from datetime import timedelta


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")

    # Comma-separated list of allowed frontend origins, e.g.
    # "https://siteforge-web.onrender.com". Defaults to "*" for local
    # dev convenience only -- combined with supports_credentials=True
    # (app/__init__.py), Flask-CORS reflects the request's actual
    # Origin back rather than literally sending "*" (browsers reject
    # a literal wildcard alongside credentials), which means an
    # unset CORS_ORIGINS in production would accept credentialed
    # requests from ANY origin. Set this explicitly to the real
    # deployed frontend URL before going live.
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")

    # Error tracking (SRS Section 6 -- previously in requirements.txt
    # but never actually initialized anywhere; an outage would have
    # been invisible until a user complained). Empty by default:
    # sentry_sdk.init() is only called in create_app() when this is
    # actually set, so local dev without a Sentry project configured
    # doesn't try to report anywhere.
    SENTRY_DSN = os.environ.get("SENTRY_DSN", "")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://siteforge:siteforge@localhost:5432/siteforge",
    )
    # A separate, narrowly-privileged role (BYPASSRLS, SELECT-only on
    # `users`) used solely for the pre-authentication email lookup in
    # login -- see app/extensions.py:get_auth_engine for why this can't
    # just be the normal DATABASE_URL role. Defaults to DATABASE_URL so
    # single-role local setups still work; production should point this
    # at the dedicated siteforge_auth role from scripts/setup_auth_role.sql.
    AUTH_DATABASE_URL = os.environ.get("AUTH_DATABASE_URL", SQLALCHEMY_DATABASE_URI)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # pool_size/max_overflow are QueuePool (Postgres) only; SQLite (used for
    # fast unit tests) uses StaticPool and rejects these kwargs, so they're
    # applied conditionally in get_config() below rather than hardcoded here.
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # JWT (short-lived access + rotating refresh, SRS Section 6.2)
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "change-me-in-production")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    # Required for token_in_blocklist_loader (app/__init__.py) to
    # actually run -- without these two, the callback is registered
    # but flask-jwt-extended never calls it, and revocation silently
    # does nothing. Only "refresh" is checked: refresh tokens are the
    # only ones ever individually revoked (logout, rotation) in this
    # codebase, and access tokens are short-lived (15 min) by design,
    # so checking them too would add a Redis round-trip to every single
    # API request for no actual benefit.
    JWT_BLOCKLIST_ENABLED = True
    JWT_BLOCKLIST_TOKEN_CHECKS = ["refresh"]

    # Redis / Celery (SRS Section 3.1, 13.2)
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", REDIS_URL)

    # Object storage (S3-compatible, SRS Section 3.1)
    S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL", "http://localhost:9000")
    S3_BUCKET = os.environ.get("S3_BUCKET", "siteforge-documents")
    S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "")
    S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "")
    # Deliberately a separate bucket from S3_BUCKET, not a prefix
    # within it -- see docs/DATA_PROTECTION.md's recommendation for
    # why: a database backup and a tenant's own uploaded documents
    # have different sensitivity, retention, and access-control needs,
    # and isolating them means a bucket-policy mistake on one doesn't
    # expose the other.
    S3_BACKUP_BUCKET = os.environ.get("S3_BACKUP_BUCKET", "siteforge-backups")

    # Anthropic API (AI Construction Assistant, SRS Section 3.6)
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    AI_ASSISTANT_MODEL = os.environ.get("AI_ASSISTANT_MODEL", "claude-sonnet-4-6")

    # Rate limiting (SRS Section 6.6)
    RATE_LIMIT_DEFAULT = "600/minute"
    RATE_LIMIT_AI = "60/minute"

    # Mobile sync (SRS Section 6.6)
    SYNC_MAX_BATCH_SIZE = 500


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_ENGINE_OPTIONS = {**BaseConfig.SQLALCHEMY_ENGINE_OPTIONS, "pool_size": 10, "max_overflow": 20}


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg2://siteforge:siteforge@localhost:5432/siteforge_test",
    )
    # Left at pool_pre_ping-only (BaseConfig default) so tests can point at
    # SQLite (TEST_DATABASE_URL=sqlite:///:memory:) for fast, dependency-free
    # unit tests, while a real Postgres CI run uses the same config class.

    # The existing test suite (95 tests as of this writing) predates
    # rate limiting and issues many requests to the same endpoint
    # (e.g. login, signup) from the same test-client IP in quick
    # succession -- real limits would start failing tests that have
    # nothing to do with rate limiting itself.
    RATELIMIT_ENABLED = False


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_ENGINE_OPTIONS = {**BaseConfig.SQLALCHEMY_ENGINE_OPTIONS, "pool_size": 10, "max_overflow": 20}


_CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name: str = None):
    name = name or os.environ.get("FLASK_ENV", "development")
    return _CONFIGS.get(name, DevelopmentConfig)
