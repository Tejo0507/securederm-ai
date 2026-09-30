"""Outbound email — currently just account-verification messages.

Uses smtplib against whatever SMTP account is configured via env vars
(SMTP_HOST/SMTP_USER/SMTP_PASSWORD — e.g. a Gmail address with an App
Password, or any other provider's SMTP credentials). No third-party
email API or paid service required.

If no SMTP account is configured, sending degrades to logging the
message instead of raising — signup must still work in a machine that
hasn't set these up, it just can't prove the address is real yet.
"""

import logging
import smtplib
from email.message import EmailMessage

from config.settings import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    SMTP_FROM_ADDRESS,
    SMTP_USE_TLS,
    EMAIL_SENDING_CONFIGURED,
    FRONTEND_URL,
    EMAIL_VERIFICATION_TOKEN_TTL_HOURS,
)

logger = logging.getLogger("web_backend.email")


def build_verification_link(token: str) -> str:
    return f"{FRONTEND_URL}/verify-email?token={token}"


def send_verification_email(to_email: str, hospital_name: str, token: str) -> None:
    link = build_verification_link(token)

    if not EMAIL_SENDING_CONFIGURED:
        logger.warning(
            "SMTP is not configured — not actually sending a verification "
            "email to %s. Verification link (dev mode only): %s",
            to_email,
            link,
        )
        return

    message = EmailMessage()
    message["Subject"] = "Verify your SecureDerm AI hospital account"
    message["From"] = SMTP_FROM_ADDRESS
    message["To"] = to_email
    message.set_content(
        f"Hi {hospital_name},\n\n"
        "Confirm this email address to activate your SecureDerm AI hospital "
        "account:\n\n"
        f"{link}\n\n"
        f"This link expires in {EMAIL_VERIFICATION_TOKEN_TTL_HOURS} hours. "
        "If you didn't request this account, you can ignore this email.\n"
    )

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
            if SMTP_USE_TLS:
                smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError):
        # A downstream mail failure shouldn't 500 the signup request the
        # user is sitting in front of — they can use "resend verification"
        # once the SMTP issue is fixed. Log it loudly so it isn't missed.
        logger.exception("Failed to send verification email to %s", to_email)
