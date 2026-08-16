# Load Testing

This is a real load test, run against a real running instance of this
app on real (local, sandboxed) Postgres and Redis -- not a projection,
not a simulation. Everything below is what actually happened when it
ran, including the two real bugs it found.

## Setup

- 4 gunicorn sync workers (`gunicorn -w 4`), the same server the app
  actually runs under.
- Postgres seeded with a modest but non-trivial data volume: 200 BDC
  clients, 150 PRC vendors, 300 INV material items, 20 distinct real
  users under one tenant (`backend/loadtest/seed.py`).
- 30 simulated concurrent users (`backend/loadtest/locustfile.py`,
  via [Locust](https://locust.io)), each authenticated as one of the
  20 seeded users, running a realistic mix of list/read/create traffic
  against BDC, PRC, and INV endpoints for 60 seconds.
- Run: `locust -f loadtest/locustfile.py --headless -u 30 -r 5 -t 60s --host http://127.0.0.1:8000`

This is a sandboxed dev environment on shared infrastructure, not
dedicated production-grade hardware -- the absolute numbers below are
not a production SLA. What's real and worth trusting is the *shape*
of what the test found: two genuine bugs, both fixed, both re-verified
by running the test again afterward.

## Finding 1: per-IP rate limiting collectively throttled every user on one network

The first run failed at a ~25% error rate, every failure a `429 Too
Many Requests`. The cause: the default rate limit
(`app/extensions.py`, 200 requests/minute) was keyed on source IP.
That's fine for preventing abuse from a single anonymous source, but
wrong for authenticated traffic on a real B2B platform where many
real people legitimately share one office or site network (a common
deployment shape for this product specifically) -- 30 simulated users
sharing one local IP were all throttled against the *same* 200/minute
budget collectively, well below what even light real usage would need.

**Fix**: the default rate-limit key now prefers the authenticated
user's identity (via JWT) over IP address, falling back to IP only
when no valid token is present -- which is exactly right for the two
routes that specifically need IP-based limiting for abuse prevention,
`/auth/login` and `/onboarding/signup`, both already protected by
their own stricter per-route limits that this change doesn't affect.
See `app/extensions.py:_rate_limit_key`.

**Re-verified**: re-running the identical test after the fix (with 20
genuinely distinct authenticated identities, not one token shared
across every simulated user -- see the note in `loadtest/locustfile.py`
about why that distinction matters) dropped the failure rate from
~25% to 0.44%, with the only remaining failures on the one
unauthenticated route in the mix.

## Finding 2: health checks were sharing the anonymous rate-limit bucket

Those remaining failures were all on `/v1/health` -- an
unauthenticated route, so it correctly fell back to the IP-based
bucket, and 30 simulated users polling it collectively exceeded 200
requests/minute. In any real deployment, `/v1/health` is polled
frequently and automatically by load balancers and orchestration
tooling; rate-limiting it at all was the actual mistake, not the
limiting logic.

**Fix**: `/v1/health` is now explicitly exempted from rate limiting
(`@limiter.exempt` in `app/__init__.py`).

**Re-verified**: re-running the test again after this fix produced
**zero failures** across 1,364 requests in the 60-second window.

## Observed latency

With both fixes in place, the final clean run:

| Metric | Value |
|---|---|
| Total requests | 1,364 |
| Failures | 0 (0.00%) |
| Throughput | ~23 requests/sec sustained |
| Median latency | 14ms |
| p95 latency | 49ms |
| p99 latency | 660ms |
| Max latency | 2,602ms |

The gap between p95 (49ms, healthy) and p99/max (into the hundreds of
milliseconds to ~2.6s) is real and worth explaining rather than
hiding: it wasn't isolated to one slow endpoint -- every endpoint type
in the mix showed a similar spike at roughly the same point in the
run. Checking `pg_stat_bgwriter` immediately after confirmed a
Postgres checkpoint occurred during the test window
(`checkpoints_req = 1`, `checkpoint_write_time` ~11 seconds), which
lines up with a brief, simultaneous I/O stall across concurrent
connections -- consistent with normal checkpoint behavior, not a
per-query or missing-index problem. This wasn't tuned away in this
pass (`checkpoint_completion_target`, WAL sizing, and disk I/O
provisioning are all still at defaults), and the observation itself
hasn't been reproduced across repeated runs to confirm it's exactly
what's happening rather than an artifact of this specific shared,
sandboxed environment -- it's reported here as what was actually
observed and the most likely explanation, not a confirmed root cause.

## What this does and doesn't establish

**Does**: this is the first time any concurrent, authenticated,
multi-user traffic has been run against this application at all, and
it found two genuine bugs that would have affected real usage on day
one of a real deployment with more than a handful of simultaneous
users. Both are fixed and re-verified.

**Doesn't**: this is not a production-scale test. 30 concurrent users
against a database seeded with a few hundred rows per table doesn't
say anything about behavior at real production data volumes (tens of
thousands of rows per tenant, many tenants) or real production
concurrency (hundreds of simultaneous users). The RPO/RTO discussion
in `docs/DATA_PROTECTION.md` already flags that a realistically-sized
timed drill hasn't been run either -- the same caveat applies here.
Before a real production launch, this should be re-run against
production-representative data volume and on infrastructure that
matches (or exceeds) the real deployment target, with the checkpoint
tuning question above actually investigated rather than left as an
observation.
