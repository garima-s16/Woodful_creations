import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from typing import Optional
import logging

from app.platform.configuration.config import settings

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.sender_email = settings.SENDER_EMAIL
        self.sender_password = settings.SENDER_PASSWORD
        self.sender_name = settings.SENDER_NAME

    def send_email(self, to_email: str, subject: str, body: str, is_html: bool = False,
                    attachment_bytes: Optional[bytes] = None, attachment_filename: Optional[str] = None) -> bool:
        try:
            if not all([self.sender_email, self.sender_password]):
                logger.warning("Email configuration missing")
                return False

            msg = MIMEMultipart()
            msg['From'] = f"{self.sender_name} <{self.sender_email}>"
            msg['To'] = to_email
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'html' if is_html else 'plain'))

            if attachment_bytes is not None and attachment_filename:
                part = MIMEApplication(attachment_bytes, Name=attachment_filename)
                part['Content-Disposition'] = f'attachment; filename="{attachment_filename}"'
                msg.attach(part)

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)

            logger.info(f"Email sent to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Email send failed: {str(e)}")
            return False