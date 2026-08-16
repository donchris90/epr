"""
Real email dispatch via SMTP -- standard library only (smtplib +
email.mime), no new dependency needed. Configured for Gmail SMTP by
default (app/config.py's SMTP_HOST), but works with any real SMTP
provider that accepts STARTTLS username/password auth.

Deliberately synchronous, single-purpose (send one email, return
whether it worked) -- the retry/async/never-block-the-main-transaction
requirements live one layer up, in app/notifications/tasks.py, which
is what actually gets called from request-handling code. This module
has no opinion about queuing; it just knows how to talk to an SMTP
server.
"""
import logging
import smtplib
from email.mime.text import MIMEText

from flask import current_app

logger = logging.getLogger(__name__)


def send_email(*, to_address: str, subject: str, body: str) -> bool:
    """
    Returns True if the email was handed off to the SMTP server
    successfully, False otherwise -- never raises. A notification
    failing to email is a real problem worth logging, but it must
    never be allowed to crash or roll back whatever business
    transaction triggered it (the same requirement that keeps this
    entirely out of the synchronous request path in the first place;
    see app/notifications/tasks.py).
    """
    host = current_app.config["SMTP_HOST"]
    port = current_app.config["SMTP_PORT"]
    username = current_app.config["SMTP_USERNAME"]
    password = current_app.config["SMTP_PASSWORD"]
    from_address = current_app.config["SMTP_FROM_ADDRESS"]
    use_tls = current_app.config["SMTP_USE_TLS"]

    if not username or not password:
        # Not a failure -- a tenant/deployment that hasn't configured
        # SMTP yet should keep working normally on in-app notifications
        # alone. Logged at info, not warning/error, since this is the
        # expected state until someone actually sets SMTP_USERNAME/
        # SMTP_PASSWORD.
        logger.info("Email dispatch skipped (SMTP not configured): %s", subject)
        return False

    if not to_address:
        logger.warning("Email dispatch skipped: no recipient address for %r", subject)
        return False

    message = MIMEText(body or "", "plain", "utf-8")
    message["Subject"] = subject
    message["From"] = from_address
    message["To"] = to_address

    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            if use_tls:
                server.starttls()
            server.login(username, password)
            server.sendmail(from_address, [to_address], message.as_string())
        return True
    except (smtplib.SMTPException, OSError) as exc:
        # OSError covers connection-level failures (DNS, timeout,
        # refused) that smtplib doesn't wrap in an SMTPException.
        logger.warning("Email dispatch failed for %r to %s: %s", subject, to_address, exc)
        return False
