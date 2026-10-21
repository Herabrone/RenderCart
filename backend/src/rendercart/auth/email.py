import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage
from urllib.parse import urlsplit

from rendercart.core.config import get_settings


def send_auth_link(email: str, token: str, purpose: str) -> None:
    settings = get_settings()
    message = EmailMessage()
    message["Subject"] = {
        "verify_email": "Verify your RenderCart email",
        "magic_link": "Your RenderCart sign-in link",
        "reset_password": "Reset your RenderCart password",
    }[purpose]
    message["From"] = settings.email_from
    message["To"] = email
    action = (
        "verify"
        if purpose == "verify_email"
        else "sign-in"
        if purpose == "magic_link"
        else "password-reset"
    )
    link = f"{settings.app_base_url}/auth/{action}?token={token}"
    message.set_content(
        f"Use this one-time link within {settings.auth_token_ttl_minutes} minutes:\n\n{link}\n"
    )
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        smtp.send_message(message)


def send_monitor_alert(
    email: str,
    monitor_name: str,
    target_url: str,
    *,
    recovered: bool,
    status_code: int | None,
    error_code: str | None,
) -> None:
    settings = get_settings()
    host = urlsplit(target_url).hostname or "unknown host"
    state = "recovered" if recovered else "is down"
    message = EmailMessage()
    message["Subject"] = f"RenderCart monitor {state}: {monitor_name}"
    message["From"] = settings.email_from
    message["To"] = email
    details = (
        f"HTTP status: {status_code}" if status_code is not None else f"Check error: {error_code}"
    )
    message.set_content(
        f"Your RenderCart uptime monitor '{monitor_name}' for {host} {state}.\n\n"
        f"{details}\n"
    )
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        smtp.send_message(message)


def send_domain_expiry_alert(
    email: str,
    domain: str,
    *,
    tls_expiry: datetime | None,
    domain_expiry: datetime | None,
) -> None:
    settings = get_settings()
    message = EmailMessage()
    message["Subject"] = f"RenderCart expiry alert: {domain}"
    message["From"] = settings.email_from
    message["To"] = email
    lines = [f"Expiry dates for {domain} are within 30 days or have passed:", ""]
    if tls_expiry is not None:
        lines.append(f"TLS certificate: {tls_expiry.astimezone(UTC).date().isoformat()} UTC")
    if domain_expiry is not None:
        lines.append(f"Domain registration: {domain_expiry.astimezone(UTC).date().isoformat()} UTC")
    message.set_content("\n".join(lines) + "\n")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        smtp.send_message(message)
