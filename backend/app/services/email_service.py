"""SMTP e-mail service for transactional messages."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.settings import settings


class EmailService:
    @staticmethod
    def _build_sender() -> str:
        if settings.SMTP_FROM_NAME and settings.SMTP_FROM_EMAIL:
            return f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        return settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME

    @staticmethod
    def send_password_reset_code(to_email: str, code: str, expires_minutes: int) -> None:
        if not settings.SMTP_HOST or not (settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME):
            raise RuntimeError("SMTP não configurado para envio de recuperação de senha")

        message = EmailMessage()
        message["Subject"] = f"{settings.PROJECT_NAME} - Código de recuperação de senha"
        message["From"] = EmailService._build_sender()
        message["To"] = to_email

        text_body = (
            f"Seu código de recuperação é: {code}\n\n"
            f"Este código expira em {expires_minutes} minutos.\n"
            "Se você não solicitou a troca de senha, ignore este e-mail."
        )
        html_body = (
            "<div style=\"font-family:Arial,sans-serif;color:#0f172a;line-height:1.5\">"
            f"<h2 style=\"margin-bottom:8px\">{settings.PROJECT_NAME}</h2>"
            "<p>Recebemos uma solicitação para redefinir sua senha.</p>"
            f"<p style=\"font-size:28px;font-weight:700;letter-spacing:6px;color:#1d4ed8\">{code}</p>"
            f"<p>Este código expira em <strong>{expires_minutes} minutos</strong>.</p>"
            "<p>Se você não solicitou a troca de senha, ignore este e-mail.</p>"
            "</div>"
        )

        message.set_content(text_body)
        message.add_alternative(html_body, subtype="html")

        if settings.SMTP_USE_SSL:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
                if settings.SMTP_USERNAME:
                    smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                smtp.send_message(message)
            return

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
            smtp.ehlo()
            if settings.SMTP_USE_TLS:
                smtp.starttls()
                smtp.ehlo()
            if settings.SMTP_USERNAME:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            smtp.send_message(message)
