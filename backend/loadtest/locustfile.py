"""
Real load test against a real running instance of this app -- not a
simulation, not mocked endpoints. Requires the Flask app actually
running (see backend/loadtest/run.sh) and the seed data created by
backend/loadtest/seed.py.

Run: locust -f loadtest/locustfile.py --headless -u <users> -r <spawn-rate> -t <duration> --host http://127.0.0.1:8000
"""
import itertools
import random
import threading

from locust import HttpUser, task, between

# Pre-authenticated outside the timed run (see the load-test session
# notes in README.md) specifically to decouple two different things:
# the login endpoint's own rate limit (10/minute per IP, already
# verified separately and unaffected by this) from what this test
# actually measures -- real authenticated request throughput against
# real Postgres. 20 distinct real users so the per-user rate-limit key
# (app/extensions.py:_rate_limit_key) is genuinely exercised the way
# many different people on one office network would use it, not one
# identity's token shared across every simulated session.
with open("/tmp/loadtest_tokens.txt") as f:
    _tokens = [line.strip() for line in f if line.strip()]

_counter = itertools.count()
_lock = threading.Lock()


class SiteForgeUser(HttpUser):
    wait_time = between(0.5, 2)

    def on_start(self):
        with _lock:
            n = next(_counter)
        token = _tokens[n % len(_tokens)]
        self.headers = {"Authorization": f"Bearer {token}"}

    @task(5)
    def list_clients(self):
        # Real pagination through a 200-row table -- the exact query
        # shape every list endpoint in this app uses.
        page = random.randint(1, 5)
        self.client.get(f"/v1/bdc/clients?page={page}&per_page=20", headers=self.headers, name="/v1/bdc/clients [list]")

    @task(5)
    def list_vendors(self):
        self.client.get("/v1/prc/vendors?per_page=20", headers=self.headers, name="/v1/prc/vendors [list]")

    @task(5)
    def list_material_items(self):
        self.client.get("/v1/inv/material-items?per_page=20", headers=self.headers, name="/v1/inv/material-items [list]")

    @task(2)
    def create_client(self):
        n = random.randint(100000, 999999)
        self.client.post(
            "/v1/bdc/clients",
            json={"name": f"Load Test Client {n}"},
            headers=self.headers,
            name="/v1/bdc/clients [create]",
        )

    @task(1)
    def check_reorder_levels(self):
        # A real cross-table read (joins stock + reorder config) --
        # the kind of query most likely to show an index gap under load.
        self.client.get("/v1/inv/reorder-levels/below-threshold", headers=self.headers, name="/v1/inv/reorder-levels/below-threshold")

    @task(3)
    def health(self):
        self.client.get("/v1/health", name="/v1/health")
