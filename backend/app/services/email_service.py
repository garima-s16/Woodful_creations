import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from datetime import datetime
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

class EmailService:
    def __init__(self):
        self.sender_email = os.getenv("EMAIL_USER", "your-email@gmail.com")
        self.sender_password = os.getenv("EMAIL_PASSWORD", "your-app-password")
        self.smtp_server = os.getenv("EMAIL_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("EMAIL_PORT", "587"))
        self.business_owner_email = os.getenv("BUSINESS_OWNER_EMAIL", "owner@example.com")
    
    def send_email(self, recipient: str, subject: str, body: str, html_body: str = None, 
                   attachments: List[tuple] = None) -> bool:
        """
        Send email notification
        
        Args:
            recipient: Email recipient
            subject: Email subject
            body: Plain text body
            html_body: HTML body (optional)
            attachments: List of (filename, filepath) tuples
        
        Returns:
            True if sent successfully
        """
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.sender_email
            msg["To"] = recipient
            msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")
            
            # Add plain text
            part1 = MIMEText(body, "plain")
            msg.attach(part1)
            
            # Add HTML if provided
            if html_body:
                part2 = MIMEText(html_body, "html")
                msg.attach(part2)
            
            # Add attachments
            if attachments:
                for filename, filepath in attachments:
                    self._attach_file(msg, filename, filepath)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            return True
        except Exception as e:
            print(f"Error sending email: {str(e)}")
            return False
    
    def _attach_file(self, msg, filename: str, filepath: str):
        """Attach file to email"""
        try:
            with open(filepath, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
            
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename= {filename}")
            msg.attach(part)
        except Exception as e:
            print(f"Error attaching file {filename}: {str(e)}")
    
    def send_low_stock_alert(self, item_name: str, sku: str, current_qty: int, 
                            min_qty: int, item_id: int) -> bool:
        """Send low stock alert email"""
        subject = f"⚠️ LOW STOCK ALERT: {item_name} ({sku})"
        
        body = f"""
        Low Stock Alert
        
        Item: {item_name}
        SKU: {sku}
        Current Quantity: {current_qty}
        Minimum Required: {min_qty}
        
        Please reorder this item to maintain adequate stock levels.
        
        Item ID: {item_id}
        Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        html_body = f"""
        <html>
            <body>
                <h2 style="color: #d32f2f;">⚠️ Low Stock Alert</h2>
                <table border="1" cellpadding="10">
                    <tr>
                        <td><strong>Item:</strong></td>
                        <td>{item_name}</td>
                    </tr>
                    <tr>
                        <td><strong>SKU:</strong></td>
                        <td>{sku}</td>
                    </tr>
                    <tr>
                        <td><strong>Current Quantity:</strong></td>
                        <td style="color: red;">{current_qty}</td>
                    </tr>
                    <tr>
                        <td><strong>Minimum Required:</strong></td>
                        <td>{min_qty}</td>
                    </tr>
                </table>
                <p><strong>Action Required:</strong> Please reorder this item to maintain adequate stock levels.</p>
                <hr>
                <small>Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</small>
            </body>
        </html>
        """
        
        return self.send_email(self.business_owner_email, subject, body, html_body)
    
    def send_inventory_report(self, recipient: str, report_data: dict, 
                             report_file: str = None) -> bool:
        """Send inventory report email"""
        subject = f"📊 Inventory Report - {datetime.now().strftime('%B %d, %Y')}"
        
        body = f"""
        Inventory Report
        
        Total Items: {report_data.get('total_items', 0)}
        Total Value: ${report_data.get('total_value', 0):.2f}
        Low Stock Items: {report_data.get('low_stock_items', 0)}
        Average Stock Level: {report_data.get('average_stock_level', 0):.2f}
        
        See attached file for detailed report.
        """
        
        html_body = f"""
        <html>
            <body>
                <h2>📊 Inventory Report</h2>
                <table border="1" cellpadding="10">
                    <tr>
                        <td><strong>Total Items:</strong></td>
                        <td>{report_data.get('total_items', 0)}</td>
                    </tr>
                    <tr>
                        <td><strong>Total Value:</strong></td>
                        <td>${report_data.get('total_value', 0):.2f}</td>
                    </tr>
                    <tr>
                        <td><strong>Low Stock Items:</strong></td>
                        <td style="color: #ff9800;">{report_data.get('low_stock_items', 0)}</td>
                    </tr>
                    <tr>
                        <td><strong>Average Stock Level:</strong></td>
                        <td>{report_data.get('average_stock_level', 0):.2f}</td>
                    </tr>
                </table>
            </body>
        </html>
        """
        
        attachments = [(report_file, report_file)] if report_file else None
        return self.send_email(recipient, subject, body, html_body, attachments)
    
    def send_batch_import_report(self, recipient: str, import_data: dict) -> bool:
        """Send batch import summary email"""
        subject = f"📥 Batch Import Report - {import_data.get('file_name', 'Import')}"
        
        body = f"""
        Batch Import Report
        
        File: {import_data.get('file_name')}
        Total Rows: {import_data.get('total_rows', 0)}
        Successful: {import_data.get('successful_rows', 0)}
        Failed: {import_data.get('failed_rows', 0)}
        
        Imported at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        html_body = f"""
        <html>
            <body>
                <h2>📥 Batch Import Report</h2>
                <p><strong>File:</strong> {import_data.get('file_name')}</p>
                <table border="1" cellpadding="10">
                    <tr>
                        <td><strong>Total Rows:</strong></td>
                        <td>{import_data.get('total_rows', 0)}</td>
                    </tr>
                    <tr>
                        <td><strong>Successful:</strong></td>
                        <td style="color: green;">{import_data.get('successful_rows', 0)}</td>
                    </tr>
                    <tr>
                        <td><strong>Failed:</strong></td>
                        <td style="color: red;">{import_data.get('failed_rows', 0)}</td>
                    </tr>
                </table>
            </body>
        </html>
        """
        
        return self.send_email(recipient, subject, body, html_body)

# Initialize email service
email_service = EmailService()
