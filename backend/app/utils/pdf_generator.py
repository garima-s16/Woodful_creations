from io import BytesIO
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class PDFGenerator:
    def __init__(self):
        try:
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib import colors
            self.available = True
        except ImportError:
            logger.warning("ReportLab not installed. PDF generation disabled.")
            self.available = False
    
    def generate_estimate_pdf(self, estimate_data: Dict, client_data: Dict, items: List) -> Optional[BytesIO]:
        if not self.available:
            logger.error("PDF generation not available")
            return None
        
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib import colors
            
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            elements = []
            
            styles = getSampleStyleSheet()
            
            title = Paragraph("ESTIMATE", styles['Title'])
            elements.append(title)
            elements.append(Spacer(1, 0.3*inch))
            
            estimate_info = f"Estimate No: {estimate_data.get('estimate_number', 'N/A')}"
            elements.append(Paragraph(estimate_info, styles['Normal']))
            
            client_info = f"Client: {client_data.get('name', 'N/A')} | Email: {client_data.get('email', 'N/A')}"
            elements.append(Paragraph(client_info, styles['Normal']))
            
            elements.append(Spacer(1, 0.2*inch))
            
            table_data = [['Item', 'Quantity', 'Unit Price', 'Amount']]
            total_amount = 0
            for item in items:
                amount = item.get('quantity', 0) * item.get('unit_price', 0)
                table_data.append([
                    item.get('description', ''),
                    str(item.get('quantity', 0)),
                    f"Rs {item.get('unit_price', 0):,.2f}",
                    f"Rs {amount:,.2f}"
                ])
                total_amount += amount
            
            table_data.append(['', '', 'Total', f"Rs {total_amount:,.2f}"])
            
            table = Table(table_data, colWidths=[2*inch, 1*inch, 1.5*inch, 1.5*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(table)
            
            doc.build(elements)
            buffer.seek(0)
            return buffer
        except Exception as e:
            logger.error(f"PDF generation error: {str(e)}")
            return None
    
    def generate_invoice_pdf(self, invoice_data: Dict) -> Optional[BytesIO]:
        pass
    
    def generate_salary_slip_pdf(self, employee_data: Dict, salary_data: Dict) -> Optional[BytesIO]:
        pass