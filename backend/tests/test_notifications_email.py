"""
Tests for app/notifications/email.py and app/notifications/tasks.py --
real Gmail SMTP dispatch, added because in-app-only notifications
weren't enough: workflow approvals need to reach someone whether or
not they're actively looking at the app.

Uses unittest.mock for smtplib rather than a live SMTP server -- the
actual integration (real SMTP handshake, real AUTH login, real
message delivery, content verified byte-for-byte on the receiving
end) was verified manually against a real local SMTP test server
before writing this permanent suite; see README.md's session notes
for that verification. Mocking here is about fast, reliable,
credential-free CI runs, not first-time proof the feature works.
"""
from unittest.mock import patch, MagicMock

import pytest


class TestSendEmail:
    def test_returns_false_and_does_not_attempt_connection_when_smtp_not_configured(self, app):
        """The documented no-op path: a tenant/deployment that hasn't
        set SMTP_USERNAME/SMTP_PASSWORD yet keeps working normally on
        in-app notifications alone -- this must never attempt an SMTP
        connection with empty credentials."""
        app.config["SMTP_USERNAME"] = ""
        app.config["SMTP_PASSWORD"] = ""

        with app.app_context():
            with patch("smtplib.SMTP") as mock_smtp:
                from app.notifications.email import send_email

                result = send_email(to_address="test@example.com", subject="Test", body="Body")

                assert result is False
                mock_smtp.assert_not_called()

    def test_returns_false_when_no_recipient_address(self, app):
        app.config["SMTP_USERNAME"] = "sender@gmail.com"
        app.config["SMTP_PASSWORD"] = "app-password"

        with app.app_context():
            from app.notifications.email import send_email

            result = send_email(to_address="", subject="Test", body="Body")
            assert result is False

    def test_sends_via_smtp_with_correct_message_when_configured(self, app):
        app.config["SMTP_HOST"] = "smtp.gmail.com"
        app.config["SMTP_PORT"] = 587
        app.config["SMTP_USE_TLS"] = True
        app.config["SMTP_USERNAME"] = "sender@gmail.com"
        app.config["SMTP_PASSWORD"] = "app-password"
        app.config["SMTP_FROM_ADDRESS"] = "sender@gmail.com"

        with app.app_context():
            with patch("smtplib.SMTP") as mock_smtp_class:
                mock_server = MagicMock()
                mock_smtp_class.return_value.__enter__.return_value = mock_server

                from app.notifications.email import send_email

                result = send_email(to_address="recipient@example.com", subject="Approval needed", body="Please review.")

                assert result is True
                mock_smtp_class.assert_called_once_with("smtp.gmail.com", 587, timeout=10)
                mock_server.starttls.assert_called_once()
                mock_server.login.assert_called_once_with("sender@gmail.com", "app-password")
                mock_server.sendmail.assert_called_once()

                call_args = mock_server.sendmail.call_args
                assert call_args[0][0] == "sender@gmail.com"  # from
                assert call_args[0][1] == ["recipient@example.com"]  # to
                assert "Approval needed" in call_args[0][2]  # message content includes subject

    def test_does_not_raise_on_smtp_failure(self, app):
        """A down or misconfigured SMTP server must never crash
        whatever triggered the notification -- send_email absorbs the
        failure and reports it via return value, not an exception."""
        app.config["SMTP_USERNAME"] = "sender@gmail.com"
        app.config["SMTP_PASSWORD"] = "app-password"

        with app.app_context():
            with patch("smtplib.SMTP", side_effect=OSError("Connection refused")):
                from app.notifications.email import send_email

                result = send_email(to_address="recipient@example.com", subject="Test", body="Body")
                assert result is False


class TestSendEmailNotificationTask:
    def test_task_returns_success_when_send_succeeds(self, app):
        with app.app_context():
            with patch("app.notifications.tasks.send_email", return_value=True) as mock_send:
                from app.notifications.tasks import send_email_notification

                result = send_email_notification.run(to_address="test@example.com", subject="Subj", body="Body")

                assert result == {"sent": True, "to": "test@example.com"}
                mock_send.assert_called_once_with(to_address="test@example.com", subject="Subj", body="Body")

    def test_task_retries_when_send_fails(self, app):
        """Real retry behavior for transient SMTP failures -- verifies
        the task actually calls self.retry rather than silently
        swallowing a failed send."""
        with app.app_context():
            with patch("app.notifications.tasks.send_email", return_value=False):
                from app.notifications.tasks import send_email_notification

                with pytest.raises(Exception):  # Celery's Retry signal, in eager/direct-call mode
                    send_email_notification.run(to_address="test@example.com", subject="Subj", body="Body")
