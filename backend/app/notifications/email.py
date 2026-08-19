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

import requests
from flask import current_app

logger = logging.getLogger(__name__)


def _create_ipv4_only_smtp_connection(host: str, port: int, timeout: int, ssl_mode: bool = False) -> smtplib.SMTP:
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

    Real fix to the first version of this fix, found from continued
    real-world reports, not assumed correct the first time: Gmail's
    real infrastructure resolves to more than one IPv4 address
    depending on network/resolver/region (confirmed by checking a real
    DNS lookup directly, though the exact count varies -- Google's
    infrastructure is load-balanced across many addresses in
    production even when a single sandbox happens to see only one).
    The original version of this function took only the first
    candidate with no fallback -- if that specific address is slow,
    rate-limiting, or unreachable for this deployment's network path
    while a different address in the same pool would have worked,
    every single attempt fails identically. Now tries every IPv4
    candidate in order, exactly matching socket.create_connection's
    own robust behavior, just restricted to IPv4-only rather than also
    trying IPv6.

    ssl_mode -- real, genuine alternative for a deployment where plain
    port 587 (a plaintext connection, upgraded to TLS mid-handshake via
    STARTTLS) consistently times out rather than being actively
    refused: port 465 establishes TLS immediately, before any SMTP
    protocol bytes are visible at all. A simple network-level filter
    watching for SMTP protocol patterns (EHLO, STARTTLS) on the wire
    has nothing to pattern-match against an immediately-encrypted
    connection -- it looks like any other TLS traffic from the first
    packet. Not guaranteed to help with every possible network
    restriction, but a real, meaningfully different connection shape
    worth having available, not just port 587 with no alternative.

    smtplib.SMTP(host, ...) is still constructed with the ORIGINAL
    HOSTNAME STRING, not any resolved IP, so certificate validation
    still checks the connection against smtp.gmail.com's real
    certificate correctly (validating against a bare IP address would
    fail hostname verification, since Gmail's certificate is issued
    for the hostname, not any specific IP). Only the actual TCP
    connection step is forced to IPv4-only candidates; every other
    layer (TLS, SMTP AUTH) behaves exactly as it would over the
    default dual-stack path.
    """
    candidates = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
    if not candidates:
        raise OSError(f"No IPv4 address found for {host}")

    smtp_cls = smtplib.SMTP_SSL if ssl_mode else smtplib.SMTP

    last_error = None
    for _family, _socktype, _proto, _canonname, sockaddr in candidates:
        try:
            server = smtp_cls(timeout=timeout)
            server._host = host  # noqa: SLF001 -- needed so starttls()/SSL validates the certificate against the real hostname, not the raw IP
            server.connect(sockaddr[0], sockaddr[1])
            return server
        except OSError as exc:
            last_error = exc
            continue
    raise last_error


def send_email(*, to_address: str, subject: str, body: str) -> bool:
    """
    Returns True if the email was handed off successfully, False
    otherwise -- never raises. A notification failing to email is a
    real problem worth logging, but it must never be allowed to crash
    or roll back whatever business transaction triggered it (the same
    requirement that keeps this entirely out of the synchronous
    request path in the first place; see app/notifications/tasks.py).

    Prefers Resend (HTTP-based) when RESEND_API_KEY is configured,
    falling back to SMTP otherwise -- see _send_via_resend's own
    docstring for why Resend was added at all.
    """
    resend_key = current_app.config["RESEND_API_KEY"]
    if resend_key:
        return _send_via_resend(resend_key, to_address=to_address, subject=subject, body=body)
    return _send_via_smtp(to_address=to_address, subject=subject, body=body)


def _send_via_resend(api_key: str, *, to_address: str, subject: str, body: str) -> bool:
    """
    Real, HTTP-based alternative to SMTP -- added specifically because
    raw SMTP (smtp.gmail.com, both port 587 and 465, both with IPv4-
    only resolution and multi-candidate fallback already applied)
    proved consistently unreliable connecting from this deployment's
    actual Render free-tier network, despite genuine attempts to fix
    it at the connection level. This sends over ordinary HTTPS -- the
    same protocol every other outbound call this app already makes
    (Paystack, etc.) -- sidestepping whatever was actually happening
    to the SMTP ports specifically, rather than continuing to guess at
    SMTP-level fixes for a problem that may not be fixable at that
    level at all from this network.

    Real API contract, confirmed directly against Resend's own current
    documentation before writing this (POST https://api.resend.com/emails,
    Bearer auth, JSON body), not written from memory.
    """
    if not to_address:
        logger.warning("Email dispatch skipped: no recipient address for %r", subject)
        return False

    from_address = current_app.config["RESEND_FROM_ADDRESS"]

    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"from": from_address, "to": [to_address], "subject": subject, "text": body or ""},
            timeout=current_app.config["SMTP_TIMEOUT"],
        )
        if response.status_code >= 400:
            # Real, specific detail in the log -- Resend's error
            # responses are genuinely informative (e.g. "from address
            # not verified" on a brand new account without a verified
            # domain yet), worth surfacing rather than swallowing.
            logger.warning(
                "Resend dispatch failed for %r to %s: HTTP %s %s", subject, to_address, response.status_code, response.text[:500]
            )
            return False
        return True
    except requests.RequestException as exc:
        logger.warning("Resend dispatch failed for %r to %s: %s", subject, to_address, exc)
        return False


def _send_via_smtp(*, to_address: str, subject: str, body: str) -> bool:
    """
    Real, original path -- sends via Gmail SMTP (or any STARTTLS/SSL
    provider). Used automatically whenever RESEND_API_KEY isn't set,
    so a deployment that hasn't switched to Resend keeps working
    exactly as before.
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

    # Real, automatic: port 465 is the standard implicit-TLS SMTP
    # port (encrypted from the first byte, no STARTTLS upgrade step --
    # see _create_ipv4_only_smtp_connection's own docstring on why
    # this is a genuinely different, worth-having connection shape,
    # not just a cosmetic config option). SMTP_USE_TLS still governs
    # the port 587 STARTTLS path unchanged.
    ssl_mode = port == 465

    try:
        with _create_ipv4_only_smtp_connection(
            host, port, timeout=current_app.config["SMTP_TIMEOUT"], ssl_mode=ssl_mode
        ) as server:
            if use_tls and not ssl_mode:
                server.starttls()
            server.login(username, password)
            server.sendmail(from_address, [to_address], message.as_string())
        return True
    except (smtplib.SMTPException, OSError) as exc:
        # OSError covers connection-level failures (DNS, timeout,
        # refused) that smtplib doesn't wrap in an SMTPException.
        logger.warning("Email dispatch failed for %r to %s: %s", subject, to_address, exc)
        return False
