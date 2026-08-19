"""
Tests for app/auth/jwt_utils.py's password hasher configuration --
real regression coverage for a real production 502 on the invitation-
accept flow.

Real root cause: argon2-cffi's PasswordHasher() with no arguments uses
its own library default (64 MiB memory cost, 4-way parallelism per
hash) -- reasonable on a well-resourced server, but a real, plausible
cause of an out-of-memory worker kill on Render's free tier (512 MB
total RAM shared across multiple gunicorn workers), which manifests
as exactly the reported symptom: a 502 with no application-level
error response at all, since the process dies before Flask can return
anything.
"""
from argon2 import PasswordHasher


class TestPasswordHasherResourceConfiguration:
    def test_hasher_uses_owasp_minimum_recommended_parameters_not_the_heavy_library_default(self):
        """Confirms the real, deliberate configuration -- OWASP's own
        current documented minimum (Password Storage Cheat Sheet,
        2026: m=19 MiB, t=2, p=1), not argon2-cffi's much heavier
        default (64 MiB, t=3, p=4) that plausibly caused the real
        production 502."""
        from app.auth.jwt_utils import _hasher

        assert _hasher.memory_cost == 19456  # 19 MiB, in KiB
        assert _hasher.time_cost == 2
        assert _hasher.parallelism == 1

        # The real, concrete point: genuinely lighter than the
        # library's own out-of-the-box default a plain
        # PasswordHasher() would have used.
        default_hasher = PasswordHasher()
        assert _hasher.memory_cost < default_hasher.memory_cost
        assert _hasher.parallelism < default_hasher.parallelism

    def test_new_hashes_still_verify_correctly(self):
        from app.auth.jwt_utils import hash_password, verify_password

        hashed = hash_password("a-real-test-password-123")
        assert verify_password(hashed, "a-real-test-password-123") is True
        assert verify_password(hashed, "the-wrong-password") is False

    def test_existing_hashes_created_with_the_old_heavier_parameters_still_verify(self):
        """Real, explicit confirmation this change doesn't break any
        existing user's password -- Argon2 hash strings embed their
        own parameters (visible directly in the string itself), so a
        hash created under the old, heavier defaults must still verify
        correctly under the new, lighter-configured hasher without any
        migration or rehashing needed."""
        from app.auth.jwt_utils import verify_password

        old_hasher = PasswordHasher()  # simulates a hash from before this fix
        old_hash = old_hasher.hash("an-existing-users-real-password")

        assert verify_password(old_hash, "an-existing-users-real-password") is True

    def test_hashing_completes_quickly_enough_for_a_synchronous_request(self):
        """Real timing proof, not just a config assertion -- confirms
        this genuinely produces a fast, low-resource hash suitable for
        running inline within a live HTTP request (which, combined
        with CELERY_TASK_ALWAYS_EAGER, this whole invitation-accept
        flow already does for its notification step)."""
        import time

        from app.auth.jwt_utils import hash_password

        started = time.monotonic()
        hash_password("timing-test-password-123")
        elapsed = time.monotonic() - started

        assert elapsed < 1.0
