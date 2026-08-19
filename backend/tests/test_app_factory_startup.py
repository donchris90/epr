"""
Tests for real startup validation (app/__init__.py:create_app) --
added after a real production incident: an invitation email went out
with a working http://localhost:5173 link instead of the real
deployed frontend, because FRONTEND_URL was never set on Render,
silently falling back to the local-dev default with no warning
anywhere.

Uses caplog rather than a subprocess -- the config value itself is
read at class-definition time (see app/config.py), so these tests
patch app.config directly after construction to exercise the actual
warning logic in create_app, rather than trying to re-import config
modules with different environment variables mid-process.
"""
import logging


class TestFrontendUrlStartupValidation:
    def test_warns_when_frontend_url_is_the_localhost_default_in_production(self, caplog):
        from app import create_app

        with caplog.at_level(logging.WARNING):
            create_app("production")

        assert any("FRONTEND_URL" in record.message for record in caplog.records)

    def test_does_not_warn_in_development(self, caplog):
        from app import create_app

        with caplog.at_level(logging.WARNING):
            create_app("development")

        assert not any("FRONTEND_URL" in record.message for record in caplog.records)

    def test_does_not_warn_when_frontend_url_is_genuinely_configured(self, caplog):
        """The real, correct case -- FRONTEND_URL patched to a real
        value (matching what a genuinely configured Render deployment
        looks like) before create_app runs, confirming the warning
        condition itself is correct, not just that it happens to fire
        with the untouched default."""
        from unittest.mock import patch

        from app import create_app
        from app.config import ProductionConfig

        with patch.object(ProductionConfig, "FRONTEND_URL", "https://siteforge-web.onrender.com"):
            with caplog.at_level(logging.WARNING):
                create_app("production")

        assert not any("FRONTEND_URL" in record.message for record in caplog.records)
