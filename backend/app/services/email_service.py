"""Email service for sending emails via SMTP."""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.settings import settings

logger = logging.getLogger(__name__)


def _build_reset_html(code: str, expires_minutes: int) -> str:
    return f"""\
<div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;padding:24px">
  <h2 style="color:#333">Código de recuperação de senha</h2>
  <p>Use o código abaixo para redefinir sua senha no <strong>{settings.PROJECT_NAME}</strong>:</p>
  <div style="font-size:32px;font-weight:bold;letter-spacing:6px;text-align:center;
              background:#f4f4f4;padding:16px;border-radius:8px;margin:24px 0">
    {code}
  </div>
  <p style="color:#666;font-size:14px">Este código expira em <strong>{expires_minutes} minuto(s)</strong>.</p>
  <p style="color:#999;font-size:12px">Se você não solicitou esta recuperação, ignore este e-mail.</p>
</div>"""


def _send_smtp(to_email: str, subject: str, html_body: str) -> None:
    host = settings.SMTP_HOST
    if not host:
        logger.warning("SMTP_HOST not configured; email to %s will only be logged", to_email)
        return

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    port = settings.SMTP_PORT
    use_ssl = settings.SMTP_USE_SSL
    use_tls = settings.SMTP_USE_TLS

    if use_ssl:
        server = smtplib.SMTP_SSL(host, port, timeout=15)
    else:
        server = smtplib.SMTP(host, port, timeout=15)

    try:
        if use_tls and not use_ssl:
            server.starttls()
        if settings.SMTP_USERNAME:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM_EMAIL, [to_email], msg.as_string())
        logger.info("email_sent to=%s subject=%s", to_email, subject)
    finally:
        server.quit()


class EmailService:
    """Email service for sending emails."""

    @staticmethod
    def send_password_reset_code(to_email: str, code: str, expires_minutes: int) -> None:
        logger.info(
            "PASSWORD_RESET_EMAIL to=%s expires_minutes=%s",
            to_email,
            expires_minutes,
        )
        subject = f"[{settings.PROJECT_NAME}] Código de recuperação de senha"
        html = _build_reset_html(code, expires_minutes)
        _send_smtp(to_email, subject, html)
