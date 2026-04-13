"""Email service for sending emails (stub implementation)."""
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Email service for sending emails."""

    @staticmethod
    def send_password_reset_code(to_email: str, code: str, expires_minutes: int) -> None:
        """Send password reset code to email.
        
        Args:
            to_email: Recipient email address
            code: Reset code to include in email
            expires_minutes: How many minutes the code is valid for
        """
        logger.info(
            "PASSWORD_RESET_EMAIL to=%s code=%s expires_minutes=%s",
            to_email,
            code,
            expires_minutes
        )
        # TODO: Implement actual email sending (e.g., SendGrid, SMTP, etc.)
        # For now, just log it for development/testing
