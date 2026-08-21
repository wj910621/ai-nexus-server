"""Email service for verification codes and password reset.

In desktop mode (CS_DESKTOP_MODE=1) or when SMTP is not configured,
all send operations silently succeed (no-op). This allows the auth
flows to work end-to-end in tests and desktop without a real SMTP server.
"""
import secrets

from loguru import logger

from app.core.config import settings


class EmailService:
    """SMTP-based email sender with graceful no-op fallback."""

    def __init__(self):
        self._enabled = self._check_enabled()

    def _check_enabled(self) -> bool:
        """Check if email sending is enabled."""
        import os
        if os.environ.get("CS_DESKTOP_MODE", "").lower() in ("1", "true", "yes"):
            return False
        return bool(settings.smtp_host)

    def generate_verification_code(self) -> str:
        """Generate a 6-digit numeric verification code."""
        return f"{secrets.randbelow(1000000):06d}"

    async def send_verification_email(self, email: str, code: str) -> bool:
        """Send verification code email. Returns True on success or skip."""
        if not self._enabled:
            logger.debug(f"Email disabled: would send verification code {code} to {email}")
            return True
        try:
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            import aiosmtplib

            msg = MIMEMultipart("alternative")
            msg["From"] = settings.smtp_from_email
            msg["To"] = email
            msg["Subject"] = "Y·NEX Story Studio - 邮箱验证码"
            text = f"您的验证码是: {code}\n该验证码 10 分钟内有效。"
            html = f"<p>您的验证码是: <strong>{code}</strong></p><p>该验证码 10 分钟内有效。</p>"
            msg.attach(MIMEText(text, "plain", "utf-8"))
            msg.attach(MIMEText(html, "html", "utf-8"))

            await aiosmtplib.send(
                msg,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_username,
                password=settings.smtp_password,
                start_tls=settings.smtp_use_tls,
            )
            logger.info(f"Verification email sent to {email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send verification email to {email}: {e}")
            return False

    async def send_password_reset_email(self, email: str, code: str) -> bool:
        """Send password reset code email. Returns True on success or skip."""
        if not self._enabled:
            logger.debug(f"Email disabled: would send reset code {code} to {email}")
            return True
        try:
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            import aiosmtplib

            msg = MIMEMultipart("alternative")
            msg["From"] = settings.smtp_from_email
            msg["To"] = email
            msg["Subject"] = "Y·NEX Story Studio - 密码重置"
            text = f"您的密码重置验证码是: {code}\n该验证码 10 分钟内有效。如非本人操作请忽略。"
            html = f"<p>您的密码重置验证码是: <strong>{code}</strong></p><p>该验证码 10 分钟内有效。如非本人操作请忽略。</p>"
            msg.attach(MIMEText(text, "plain", "utf-8"))
            msg.attach(MIMEText(html, "html", "utf-8"))

            await aiosmtplib.send(
                msg,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_username,
                password=settings.smtp_password,
                start_tls=settings.smtp_use_tls,
            )
            logger.info(f"Password reset email sent to {email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send reset email to {email}: {e}")
            return False
