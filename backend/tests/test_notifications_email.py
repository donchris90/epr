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
            with patch("smtplib.SMTP") as mock_smtp_class, patch("socket.getaddrinfo") as mock_getaddrinfo:
                # Real shape of what getaddrinfo(..., socket.AF_INET, ...)
                # actually returns -- see
                # app/notifications/email.py:_create_ipv4_only_smtp_connection's
                # own docstring for why this exists at all.
                mock_getaddrinfo.return_value = [(2, 1, 6, "", ("142.250.1.109", 587))]
                mock_server = MagicMock()
                mock_smtp_class.return_value = mock_server
                mock_server.__enter__.return_value = mock_server

                from app.notifications.email import send_email

                result = send_email(to_address="recipient@example.com", subject="Approval needed", body="Please review.")

                assert result is True
                # The real fix: getaddrinfo is called with AF_INET
                # explicitly, not left to resolve ambiguously.
                mock_getaddrinfo.assert_called_once_with("smtp.gmail.com", 587, __import__("socket").AF_INET, __import__("socket").SOCK_STREAM)
                # smtplib.SMTP() constructed with no host -- the actual
                # connection happens via a separate .connect() call to
                # the resolved IPv4 address, not embedded in the
                # constructor the way the old, broken version did it.
                mock_smtp_class.assert_called_once_with(timeout=10)
                mock_server.connect.assert_called_once_with("142.250.1.109", 587)
                # The real point of preserving _host manually: TLS
                # certificate validation (starttls -> server_hostname=
                # self._host) must check against the real hostname,
                # never the raw IP -- Gmail's certificate is issued for
                # smtp.gmail.com, not for any specific IP address.
                assert mock_server._host == "smtp.gmail.com"
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


class TestIPv4OnlySMTPConnection:
    """
    Real regression coverage for a real production bug: Render logs
    showed [Errno 101] "Network is unreachable" connecting to
    smtp.gmail.com -- ENETUNREACH, a routing failure distinct from a
    blocked-port refusal, and the classic signature of a container
    resolving a hostname's IPv6 address with no actual IPv6 route
    configured. See app/notifications/email.py's own docstring on
    _create_ipv4_only_smtp_connection for the full diagnosis.
    """

    def test_resolves_with_af_inet_explicitly(self, app):
        import socket

        with patch("socket.getaddrinfo") as mock_getaddrinfo, patch("smtplib.SMTP") as mock_smtp_class:
            mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("142.250.1.109", 587))]
            mock_smtp_class.return_value = MagicMock()

            from app.notifications.email import _create_ipv4_only_smtp_connection

            _create_ipv4_only_smtp_connection("smtp.gmail.com", 587, timeout=10)

            args = mock_getaddrinfo.call_args[0]
            assert args[2] == socket.AF_INET  # never left ambiguous between IPv4/IPv6

    def test_connects_to_the_resolved_ipv4_address_not_the_hostname(self, app):
        with patch("socket.getaddrinfo") as mock_getaddrinfo, patch("smtplib.SMTP") as mock_smtp_class:
            mock_getaddrinfo.return_value = [(2, 1, 6, "", ("142.250.1.109", 587))]
            mock_server = MagicMock()
            mock_smtp_class.return_value = mock_server

            from app.notifications.email import _create_ipv4_only_smtp_connection

            _create_ipv4_only_smtp_connection("smtp.gmail.com", 587, timeout=10)

            mock_server.connect.assert_called_once_with("142.250.1.109", 587)

    def test_preserves_the_real_hostname_for_tls_certificate_validation(self, app):
        """The real subtlety this fix has to get right: connecting to
        a raw IP but still validating TLS against the hostname Gmail's
        certificate is actually issued for. Confirmed directly against
        CPython's own smtplib source (self._host, read by starttls's
        server_hostname= for SNI/cert validation) before writing this
        fix, not assumed."""
        with patch("socket.getaddrinfo") as mock_getaddrinfo, patch("smtplib.SMTP") as mock_smtp_class:
            mock_getaddrinfo.return_value = [(2, 1, 6, "", ("142.250.1.109", 587))]
            mock_server = MagicMock()
            mock_smtp_class.return_value = mock_server

            from app.notifications.email import _create_ipv4_only_smtp_connection

            _create_ipv4_only_smtp_connection("smtp.gmail.com", 587, timeout=10)

            assert mock_server._host == "smtp.gmail.com"

    def test_real_end_to_end_send_against_a_real_local_smtp_server(self, app):
        """Not mocked -- an actual aiosmtpd server, actual TCP
        connection, actual AUTH LOGIN exchange, actual message
        delivery, content verified on the receiving end. Confirms this
        fix doesn't just look right in isolation; a real send through
        the real, now-IPv4-forced code path genuinely still works."""
        from aiosmtpd.controller import Controller
        from aiosmtpd.smtp import AuthResult, LoginPassword

        received = []

        def authenticator(server, session, envelope, mechanism, auth_data):
            if isinstance(auth_data, LoginPassword) and auth_data.login == b"sender@example.com":
                return AuthResult(success=True)
            return AuthResult(success=False, handled=False)

        class RecordingHandler:
            async def handle_DATA(self, server, session, envelope):
                received.append((envelope.mail_from, list(envelope.rcpt_tos), envelope.content.decode("utf8")))
                return "250 Message accepted"

        controller = Controller(
            RecordingHandler(), hostname="127.0.0.1", port=18465,
            authenticator=authenticator, auth_required=True, auth_require_tls=False,
        )
        controller.start()
        try:
            app.config["SMTP_HOST"] = "127.0.0.1"
            app.config["SMTP_PORT"] = controller.port
            app.config["SMTP_USE_TLS"] = False
            app.config["SMTP_USERNAME"] = "sender@example.com"
            app.config["SMTP_PASSWORD"] = "irrelevant-for-this-fake-server"
            app.config["SMTP_FROM_ADDRESS"] = "sender@example.com"

            with app.app_context():
                from app.notifications.email import send_email

                result = send_email(to_address="real-recipient@example.com", subject="Real end-to-end test", body="Genuine content")

            assert result is True
            assert len(received) == 1
            mail_from, rcpt_tos, content = received[0]
            assert mail_from == "sender@example.com"
            assert rcpt_tos == ["real-recipient@example.com"]
            assert "Real end-to-end test" in content  # subject header, not base64-encoded

            import base64
            import re

            # The body IS base64-encoded -- that's MIMEText's normal,
            # correct behavior, not something this fix changes. Decode
            # it to confirm the real content made it through intact,
            # rather than asserting on the raw encoded bytes.
            body_match = re.search(r"\r\n\r\n(.+)\r\n", content, re.DOTALL)
            decoded_body = base64.b64decode(body_match.group(1)).decode("utf-8")
            assert decoded_body == "Genuine content"
        finally:
            controller.stop()


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
