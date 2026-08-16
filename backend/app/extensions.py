"""
Shared Flask extension instances, initialized in the app factory
(app/__init__.py) to avoid circular imports across the 25 modules.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager, get_jwt_identity, verify_jwt_in_request
from flask_cors import CORS
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from celery import Celery

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
cors = CORS()
cache = Cache()


def _rate_limit_key():
    """Per-authenticated-user, not per-IP, for the default limit.

    Found by actually running a load test (backend/loadtest/) against
    a real server: per-IP limiting throttles every user sharing one
    office/site network collectively against the same 200/minute
    budget -- a normal deployment shape for this platform (a
    construction site or office behind NAT), not an edge case. 30
    simulated users behind one local IP hit 25% failure rate on
    entirely legitimate traffic under this bug.

    Falls back to remote address when no valid JWT is present, which
    is exactly right for the two routes that need IP-based limiting
    specifically -- /auth/login and /onboarding/signup, both already
    protected by their own stricter per-route limits
    (app/auth/routes.py, app/onboarding/routes.py) that are
    unaffected by this default key function.
    """
    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        if identity:
            return f"user:{identity}"
    except Exception:
        pass
    return get_remote_address()


# Rate limiting (SRS Section 6 -- login, signup, and every write
# endpoint were previously open to unlimited brute-force/abuse).
# storage_uri is set in create_app() once REDIS_URL is known from
# config, using the same Redis instance already used for refresh-token
# revocation -- an in-memory limiter would only ever see the requests
# hitting the one worker process it happens to run in, which stops
# being a real limit once the app runs as multiple gunicorn workers.
limiter = Limiter(key_func=_rate_limit_key, default_limits=["200 per minute"])

# Celery is configured fully once the app factory has bound its config;
# see app/celery_app.py for the bound instance used by worker processes.
celery = Celery(__name__)

# --- Auth lookup ---
#
# The login endpoint's chicken-and-egg problem under RLS (finding a
# user by email requires searching *across* tenants, before the
# tenant is known) used to be solved with a second, BYPASSRLS-attribute
# Postgres role and a separate connection engine here. That approach
# turned out to be impossible to provision on a real managed Postgres
# deployment: Postgres requires the granting role to itself have
# BYPASSRLS to hand that attribute to anyone else, which blocked every
# login in production with no self-service fix available. Replaced by
# app/models/core.py:EmailTenantIndex -- a small table deliberately
# outside RLS entirely, queried through the normal db.session like
# everything else. No special role, no separate engine, nothing here
# anymore.


# --- Redis client (refresh-token revocation, SRS Section 6.2) ---
#
# Lazily created for the same reason as the auth engine: importing this
# module shouldn't require REDIS_URL to be configured in contexts that
# never touch it (most unit tests). A real Redis-backed blocklist (not
# an in-process set) is what makes revocation actually work once the
# app runs as multiple gunicorn worker processes / multiple machines --
# an in-memory set is only ever visible to the one worker that set it.
_redis_client = None


def get_redis_client():
    global _redis_client
    if _redis_client is None:
        import redis
        from flask import current_app

        _redis_client = redis.from_url(current_app.config["REDIS_URL"], decode_responses=True)
    return _redis_client


# --- S3-compatible object storage client (SRS Section 3.1) ---
#
# Lazily created for the same reason as the two clients above. Uses
# path-style addressing (`addressing_style: path`) rather than the
# boto3 default virtual-hosted style, because virtual-hosted style
# requires the bucket name to resolve as a DNS subdomain of the
# endpoint (bucket.s3.amazonaws.com) -- which real AWS supports via
# wildcard DNS but self-hosted S3-compatible servers (MinIO, or the
# moto test server used in this backend's own test suite) generally
# don't, unless specifically configured for it. Path-style
# (endpoint/bucket/key) works everywhere.
_s3_client = None


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        import boto3
        from botocore.config import Config as BotoConfig
        from flask import current_app

        _s3_client = boto3.client(
            "s3",
            endpoint_url=current_app.config["S3_ENDPOINT_URL"],
            aws_access_key_id=current_app.config["S3_ACCESS_KEY"] or None,
            aws_secret_access_key=current_app.config["S3_SECRET_KEY"] or None,
            config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
            region_name="us-east-1",
        )
    return _s3_client
