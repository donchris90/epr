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
import socket
from email.mime.text import MIMEText

from flask import current_app

logger = logging.getLogger(__name__)


def _create_ipv4_only_smtp_connection(host: str, port: int, timeout: int) -> smtplib.SMTP:
    """
    Real bug found from an actual production log, not guessed:
    [Errno 101] ENETUNREACH ("Network is unreachable") is a routing
    failure, not a blocked port -- a genuinely different OS-level
    error than the [Errno 111] Connection refused a firewall/port
    block produces. The classic cause, confirmed against multiple
    independent real-world reports of this exact error connecting to
    smtp.gmail.com from a container: getaddrinfo() resolves the
    hostname to both an IPv4 and an IPv6 address, Python's default
    socket.create_connection() tries them in the order returned (often
    IPv6 first), and many container/cloud network configurations have
    no actual IPv6 route -- so that first attempt fails immediately at
    the kernel level, before any SMTP handshake is even possible.

    Fixed by resolving the real IPv4 address ourselves and connecting
    directly to it -- but smtplib.SMTP(host, ...) is still constructed
    with the ORIGINAL HOSTNAME STRING, not the resolved IP, so
    starttls()'s certificate validation still checks the connection
    against smtp.gmail.com's real certificate correctly (validating
    against a bare IP address would fail hostname verification, since
    Gmail's certificate is issued for the hostname, not any specific
    IP). Only the actual TCP connection step is forced to IPv4; every
    other layer (TLS, SMTP AUTH) behaves exactly as it would over the
    default dual-stack path.
    """
    ipv4_address = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)[0][4]

    server = smtplib.SMTP(timeout=timeout)
    server._host = host  # noqa: SLF001 -- needed so starttls() validates the certificate against the real hostname, not the raw IP
    server.connect(ipv4_address[0], ipv4_address[1])
    return server


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
        with _create_ipv4_only_smtp_connection(host, port, timeout=10) as server:
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
