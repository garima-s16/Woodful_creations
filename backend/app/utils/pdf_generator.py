"""Order estimate PDF generation (reportlab Platypus)."""
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from app.models.order import Order


def generate_order_estimate_pdf(order: Order) -> BytesIO:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.6 * inch, bottomMargin=0.6 * inch)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("WOODFUL CREATIONS", styles["Title"]))
    elements.append(Paragraph("Order Estimate", styles["Heading2"]))
    elements.append(Spacer(1, 0.2 * inch))

    client_name = order.client.name if order.client else "N/A"
    client_phone = order.client.phone if order.client else "N/A"
    client_address = order.client.address if order.client else "N/A"

    info_lines = [
        f"Order ID: {order.order_code}",
        f"Order Date: {order.order_date.strftime('%d-%m-%Y') if order.order_date else 'N/A'}",
        f"Delivery Date: {order.delivery_date.strftime('%d-%m-%Y') if order.delivery_date else 'N/A'}",
        f"Client: {client_name}",
        f"Phone: {client_phone}",
        f"Site Address: {order.site_address or client_address or 'N/A'}",
        f"Project Type: {order.project_type or 'N/A'}",
    ]
    for line in info_lines:
        elements.append(Paragraph(line, styles["Normal"]))
    elements.append(Spacer(1, 0.3 * inch))

    def money(v):
        return f"Rs {float(v or 0):,.2f}"

    table_data = [
        ["Description", "Amount"],
        ["Order Value", money(order.order_value)],
        ["Advance Received", money(order.advance)],
        ["Other Received", money(order.other_received)],
        ["Total Received", money(order.total_received)],
        ["Balance Due", money(order.balance)],
    ]
    table = Table(table_data, colWidths=[3.5 * inch, 2 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 11),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F2F2F2")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(table)

    elements.append(Spacer(1, 0.3 * inch))
    elements.append(Paragraph(f"Status: {order.project_status} ({order.progress_percent}% complete)", styles["Normal"]))
    if order.remarks:
        elements.append(Paragraph(f"Remarks: {order.remarks}", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer
