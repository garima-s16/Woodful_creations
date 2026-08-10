"""Order estimate PDF generation (reportlab Platypus)."""
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from app.models.order import Order
from app.models.estimate import Estimate
from app.models.salary_slip import SalarySlip


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


def generate_estimate_pdf(estimate: Estimate) -> BytesIO:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.6 * inch, bottomMargin=0.6 * inch)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("WOODFUL CREATIONS", styles["Title"]))
    elements.append(Paragraph("Cost Estimate", styles["Heading2"]))
    elements.append(Spacer(1, 0.2 * inch))

    client_name = estimate.client.name if estimate.client else "N/A"
    client_phone = estimate.client.phone if estimate.client else "N/A"
    client_address = estimate.client.address if estimate.client else "N/A"

    for line in [
        f"Estimate No: {estimate.estimate_code}",
        f"Date: {estimate.created_at.strftime('%d-%m-%Y') if estimate.created_at else 'N/A'}",
        f"Valid Until: {estimate.valid_until.strftime('%d-%m-%Y') if estimate.valid_until else 'N/A'}",
        f"Client: {client_name}",
        f"Phone: {client_phone}",
        f"Address: {client_address}",
    ]:
        elements.append(Paragraph(line, styles["Normal"]))
    if estimate.description:
        elements.append(Spacer(1, 0.1 * inch))
        elements.append(Paragraph(f"Scope: {estimate.description}", styles["Normal"]))
    elements.append(Spacer(1, 0.3 * inch))

    def money(v):
        return f"Rs {float(v or 0):,.2f}"

    table_data = [
        ["Description", "Amount"],
        ["Material Cost", money(estimate.material_cost)],
        ["Labor Cost", money(estimate.labor_cost)],
        [f"Tax ({float(estimate.tax_percent)}%)", money(estimate.tax_amount)],
        ["Total Estimate", money(estimate.total_cost)],
    ]
    table = Table(table_data, colWidths=[3.5 * inch, 2 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F2F2F2")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(table)

    elements.append(Spacer(1, 0.3 * inch))
    elements.append(Paragraph(
        "Payment Terms: As per agreed schedule. This estimate is valid until the date above; "
        "prices may change after expiry.", styles["Italic"],
    ))
    if estimate.remarks:
        elements.append(Paragraph(f"Remarks: {estimate.remarks}", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_salary_slip_pdf(slip: SalarySlip) -> BytesIO:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.6 * inch, bottomMargin=0.6 * inch)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("WOODFUL CREATIONS", styles["Title"]))
    elements.append(Paragraph(f"Salary Slip - {slip.month} {slip.year}", styles["Heading2"]))
    elements.append(Spacer(1, 0.2 * inch))

    employee_name = slip.employee.name if slip.employee else "N/A"
    department = slip.employee.department if slip.employee else "N/A"

    for line in [f"Employee: {employee_name}", f"Department: {department}", f"Status: {slip.status}"]:
        elements.append(Paragraph(line, styles["Normal"]))
    elements.append(Spacer(1, 0.3 * inch))

    def money(v):
        return f"Rs {float(v or 0):,.2f}"

    table_data = [
        ["Earnings", "Amount", "Deductions", "Amount"],
        ["Basic", money(slip.basic), "PF", money(slip.pf_deduction)],
        ["DA", money(slip.da), "TDS", money(slip.tds_deduction)],
        ["HRA", money(slip.hra), "Other", money(slip.other_deductions)],
        ["Overtime", money(slip.overtime_amount), "", ""],
        ["Net Salary", money(slip.net_salary), "", ""],
    ]
    table = Table(table_data, colWidths=[1.6 * inch, 1.6 * inch, 1.6 * inch, 1.6 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, -1), (1, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(table)

    elements.append(Spacer(1, 0.3 * inch))
    elements.append(Paragraph(
        "Note: PF/TDS figures reflect what was entered for this slip - this system does not "
        "calculate statutory deductions automatically. Confirm figures with your accountant "
        "before finalizing payroll.", styles["Italic"],
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer
