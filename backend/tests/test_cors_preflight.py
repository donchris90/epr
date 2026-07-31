"""
Regression coverage for a real production bug found only after an
actual deployed frontend made real cross-origin requests to a real
deployed backend -- something no test in this suite exercised before
(every existing test either hits a public path or supplies a valid
JWT via auth_headers/create_access_token). The whole 112-test suite
passing never caught this because nothing in it simulated a genuine
browser CORS preflight.

The bug: app/middleware/tenant_context.py's before_request hook ran
on every request to a protected path, including OPTIONS preflight,
which never carries an Authorization header (normal browser behavior).
calling get_jwt() right after verify_jwt_in_request(optional=True)
raised specifically for OPTIONS (a plain unauthenticated GET to the
same path correctly returned 403; OPTIONS raised instead), which
surfaced in production as a 500 on every single CORS preflight to any
protected route -- meaning every cross-origin frontend request to a
protected endpoint failed, full stop, since a failed preflight blocks
the browser from ever sending the real request at all.
"""


class TestCORSPreflight:
    def test_options_preflight_to_protected_route_does_not_500(self, app, client):
        r = client.options(
            "/v1/bdc/opportunities",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert r.status_code != 500
        assert r.status_code in (200, 204)

    def test_options_preflight_includes_cors_header(self, app, client):
        r = client.options(
            "/v1/bdc/opportunities",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert r.headers.get("Access-Control-Allow-Origin") is not None

    def test_unauthenticated_get_to_protected_route_still_returns_clean_403(self, app, client):
        """Confirms the fix (skipping the middleware entirely for
        OPTIONS) didn't accidentally weaken real request handling --
        a genuine unauthenticated GET must still be rejected cleanly,
        not let through."""
        r = client.get("/v1/bdc/opportunities")
        assert r.status_code == 403

    def test_health_check_unaffected(self, app, client):
        r = client.get("/v1/health")
        assert r.status_code == 200
