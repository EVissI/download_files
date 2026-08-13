"""Отправка email через SMTP."""

from __future__ import annotations

import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

from loguru import logger

from bot.config import settings


class EmailService:
    """Сервис отправки писем через SMTP."""

    @property
    def host(self) -> str | None:
        return settings.SMTP_HOST

    @property
    def port(self) -> int:
        return settings.SMTP_PORT

    @property
    def user(self) -> str | None:
        return settings.SMTP_USER

    @property
    def password(self) -> str | None:
        return settings.SMTP_PASSWORD

    @property
    def from_email(self) -> str | None:
        return settings.get_smtp_from_email()

    @property
    def from_name(self) -> str:
        return settings.SMTP_FROM_NAME

    @property
    def use_tls(self) -> bool:
        return settings.SMTP_USE_TLS

    @property
    def use_ssl(self) -> bool:
        return settings.SMTP_USE_SSL or self.port == 465

    def is_configured(self) -> bool:
        return settings.is_smtp_configured()

    def _get_smtp_connection(self) -> smtplib.SMTP:
        if self.use_ssl:
            smtp: smtplib.SMTP = smtplib.SMTP_SSL(self.host, self.port, timeout=30)
            smtp.ehlo()
        else:
            smtp = smtplib.SMTP(self.host, self.port, timeout=30)
            smtp.ehlo()
            if self.use_tls:
                smtp.starttls()
                smtp.ehlo()

        if self.user and self.password:
            if smtp.has_extn("auth"):
                smtp.login(self.user, self.password)
            else:
                logger.debug(
                    "SMTP server does not support AUTH, skipping authentication: host={}",
                    self.host,
                )

        return smtp

    def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: str | None = None,
    ) -> bool:
        if not self.is_configured():
            logger.warning("SMTP is not configured, cannot send email")
            return False

        sender_email = self.from_email
        if not sender_email or "@" not in sender_email:
            logger.error(
                "Invalid or missing SMTP from_email, cannot send email: from_email={}",
                sender_email,
            )
            return False

        to_email = to_email.strip().replace("\n", "").replace("\r", "")
        subject = subject.replace("\n", "").replace("\r", "")

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            safe_from_name = (
                self.from_name.replace("\n", "").replace("\r", "")
                if self.from_name
                else ""
            )
            safe_from_email = sender_email.replace("\n", "").replace("\r", "")
            msg["From"] = f"{safe_from_name} <{safe_from_email}>"
            msg["To"] = to_email
            msg["Date"] = formatdate(localtime=False)
            msg["Message-ID"] = make_msgid(domain=safe_from_email.split("@")[-1])

            if body_text is None:
                body_text = re.sub(r"<[^>]+>", "", body_html)
                body_text = (
                    body_text.replace("&nbsp;", " ")
                    .replace("&amp;", "&")
                    .replace("&lt;", "<")
                    .replace("&gt;", ">")
                )

            msg.attach(MIMEText(body_text, "plain", "utf-8"))
            msg.attach(MIMEText(body_html, "html", "utf-8"))

            with self._get_smtp_connection() as smtp:
                smtp.sendmail(safe_from_email, to_email, msg.as_string())

            logger.info("Email sent successfully to {}", to_email)
            return True
        except Exception as exc:
            logger.error("Failed to send email to {}: {}", to_email, exc)
            return False


email_service = EmailService()
