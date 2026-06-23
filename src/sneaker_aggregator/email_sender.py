"""Send the report as a multipart (HTML + text) email via Gmail SMTP."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from .config import Secrets

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 587


def send_email(subject: str, html_body: str, text_body: str, secrets: Secrets) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = secrets.gmail_address
    msg["To"] = secrets.recipient_email
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    context = ssl.create_default_context()
    with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as server:
        server.starttls(context=context)
        server.login(secrets.gmail_address, secrets.gmail_app_password)
        server.send_message(msg)
