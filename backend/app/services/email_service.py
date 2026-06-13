import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", 587))
        self.sender_email = os.getenv("SENDER_EMAIL")
        self.sender_password = os.getenv("SENDER_PASSWORD")
        self.sender_name = os.getenv("SENDER_NAME", "Woodful Creations")
    
    def send_email(self, to_email: str, subject: str, body: str, is_html: bool = False) -> bool:
        try:
            if not all([self.sender_email, self.sender_password]):
                logger.warning("Email configuration missing")
                return False
            
            msg = MIMEMultipart()
            msg['From'] = f"{self.sender_name} <{self.sender_email}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'html' if is_html else 'plain'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            logger.info(f"Email sent to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Email send failed: {str(e)}")
            return False
    
    def send_bulk_email(self, to_emails: List[str], subject: str, body: str) -> int:
        sent_count = 0
        for email in to_emails:
            if self.send_email(email, subject, body):
                sent_count += 1
        return sent_count
    
    def send_low_stock_alert(self, to_email: str, items: List[dict]) -> bool:
        subject = "Low Stock Alert - Woodful Creations"
        body = "<h3>Low Stock Items</h3><ul>"
        for item in items:
            body += f"<li>{item['name']}: {item['current']}/{item['minimum']} units</li>"
        body += "</ul><p>Please reorder these items soon.</p>"
        return self.send_email(to_email, subject, body, is_html=True)
    
    def send_estimate_email(self, to_email: str, client_name: str, estimate_number: str) -> bool:
        subject = f"Estimate {estimate_number} - Woodful Creations"
        body = f"<p>Dear {client_name},</p><p>Please find your estimate {estimate_number} attached.</p>"
        return self.send_email(to_email, subject, body, is_html=True)
    
    def send_payment_reminder(self, to_email: str, client_name: str, amount: float, due_date: str) -> bool:
        subject = "Payment Reminder - Woodful Creations"
        body = f"<p>Dear {client_name},</p><p>This is a reminder that Rs {amount:,.2f} is due by {due_date}.</p>"
        return self.send_email(to_email, subject, body, is_html=True)