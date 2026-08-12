"""Order estimate PDF generation (reportlab Platypus), using the shared
Woodful document design system in document_style.py."""
from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from app.models.order import Order
from app.models.estimate import Estimate
from app.models.salary_slip import SalarySlip
from app.models.payment import Payment
from app.utils.document_style import (
    format_inr, get_styles, build_header, section_table, line_items_table, build_footer_text,
    INK, GOLD, BORDER,
)


def _fmt_date(d):
    return d.strftime("%d %b %Y") if d else "-"


def generate_order_estimate_pdf(order: Order) -> BytesIO:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.6 * inch, bottomMargin=0.7 * inch,
                             leftMargin=0.6 * inch, rightMargin=0.6 * inch)
    styles = get_styles()
    elements = build_header("ORDER SUMMARY", order.order_code, _fmt_date(order.order_date), order.business_id)

    client_name = order.client.name if order.client else "-"
    client_phone = order.client.phone if order.client else "-"
    client_address = order.site_address or (order.client.address if order.client else "-")

    elements.append(section_table(
        [[("CLIENT", client_name), ("PHONE", client_phone)],
         [("PROJECT TYPE", order.project_type or "-"), ("DELIVERY DATE", _fmt_date(order.delivery_date))],
         [("SITE ADDRESS", client_address), ("STATUS", f"{order.project_status} ({order.progress_percent}% complete)")]],
        [3.5 * inch, 3.5 * inch],
    ))
    elements.append(Spacer(1, 14))

    elements.append(line_items_table(
        ["Description", "Amount"],
        [
            ["Order Value", format_inr(order.order_value)],
            ["Advance Received", format_inr(order.advance)],
            ["Other Received", format_inr(order.other_received)],
        ],
        [5 * inch, 2 * inch],
        totals_rows=[
            ["Total Received", format_inr(order.total_received)],
            ["Balance Due", format_inr(order.balance)],
        ],
    ))

    if order.remarks:
        elements.append(Spacer(1, 14))
        elements.append(Paragraph(f'<font color="#70685D" size="8">REMARKS</font><br/>{order.remarks}', styles["body"]))

    elements.append(Spacer(1, 24))
    elements.append(Paragraph(build_footer_text(), styles["footer"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_estimate_pdf(estimate: Estimate) -> BytesIO:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.6 * inch, bottomMargin=0.7 * inch,
                             leftMargin=0.6 * inch, rightMargin=0.6 * inch)
    styles = get_styles()
    elements = build_header("ESTIMATE", estimate.estimate_code, _fmt_date(estimate.created_at), estimate.business_id)

    client_name = estimate.client.name if estimate.client else "-"
    client_phone = estimate.client.phone if estimate.client else "-"
    client_address = estimate.client.address if estimate.client else "-"

    # Only surface version info when this is genuinely part of a
    # revision chain - v1 with no revisions carries no information and
    # is just noise on every ordinary estimate.
    is_revision = estimate.version > 1 or estimate.parent_estimate_id is not None
    row2_right = ("VERSION", f"v{estimate.version}") if is_revision else ("SCOPE", estimate.description or "-")

    elements.append(section_table(
        [[("CLIENT", client_name), ("PHONE", client_phone)],
         [("VALID UNTIL", _fmt_date(estimate.valid_until)), row2_right],
         [("ADDRESS", client_address), ("SCOPE", estimate.description or "-") if is_revision else ("STATUS", estimate.status.title())]],
        [3.5 * inch, 3.5 * inch],
    ))
    elements.append(Spacer(1, 14))

    if estimate.line_items:
        item_rows = [
            [item.description, item.category or "-", f"{float(item.quantity):g}", item.unit or "-",
             format_inr(item.rate), format_inr(item.amount)]
            for item in estimate.line_items
        ]
        totals_rows = [["Subtotal", "", "", "", "", format_inr(estimate.subtotal)]]
        if estimate.discount:
            totals_rows.append(["Discount", "", "", "", "", f"-{format_inr(estimate.discount)}"])
        totals_rows.append([f"GST ({float(estimate.tax_percent)}%)", "", "", "", "", format_inr(estimate.tax_amount)])
        totals_rows.append(["Grand Total", "", "", "", "", format_inr(estimate.total_cost)])
        elements.append(line_items_table(
            ["Description", "Category", "Qty", "Unit", "Rate", "Amount"],
            item_rows,
            [1.8 * inch, 1.1 * inch, 0.6 * inch, 0.7 * inch, 1.1 * inch, 1.7 * inch],
            totals_rows=totals_rows,
        ))
    else:
        # Legacy fallback for estimates created before line items existed.
        legacy_rows = [
            ["Material Cost", format_inr(estimate.material_cost)],
            ["Labor Cost", format_inr(estimate.labor_cost)],
        ]
        if estimate.discount:
            legacy_rows.append(["Discount", f"-{format_inr(estimate.discount)}"])
        legacy_rows.append([f"Tax ({float(estimate.tax_percent)}%)", format_inr(estimate.tax_amount)])
        elements.append(line_items_table(
            ["Description", "Amount"], legacy_rows, [5 * inch, 2 * inch],
            totals_rows=[["Total Estimate Value", format_inr(estimate.total_cost)]],
        ))

    elements.append(Spacer(1, 14))
    elements.append(Paragraph(
        '<font color="#70685D" size="8">PAYMENT TERMS</font><br/>'
        "As per agreed schedule. This estimate is valid until the date above; "
        "prices may change after expiry.",
        styles["body"],
    ))
    if estimate.remarks:
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(f'<font color="#70685D" size="8">REMARKS</font><br/>{estimate.remarks}', styles["body"]))

    elements.append(Spacer(1, 24))
    elements.append(Paragraph(build_footer_text(), styles["footer"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_salary_slip_pdf(slip: SalarySlip) -> BytesIO:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.6 * inch, bottomMargin=0.7 * inch,
                             leftMargin=0.6 * inch, rightMargin=0.6 * inch)
    styles = get_styles()
    elements = build_header("SALARY SLIP", f"{slip.month} {slip.year}", "", slip.business_id)

    employee_name = slip.employee.name if slip.employee else "-"
    employee_code = slip.employee.employee_code if slip.employee else "-"
    designation = (slip.employee.designation if slip.employee else None) or "-"
    department = slip.employee.department if slip.employee else "-"

    elements.append(section_table(
        [[("EMPLOYEE", employee_name), ("EMPLOYEE ID", employee_code)],
         [("DESIGNATION", designation), ("DEPARTMENT", department)],
         [("PAY PERIOD", f"{slip.month} {slip.year}"), ("STATUS", slip.status)],
         [("WORKING DAYS", str(slip.working_days)), ("PAID DAYS", str(slip.paid_days))]],
        [3.5 * inch, 3.5 * inch],
    ))
    elements.append(Spacer(1, 14))

    table_data = [
        ["Earnings", "Amount", "Deductions", "Amount"],
        ["Basic", format_inr(slip.basic), "PF", format_inr(slip.pf_deduction)],
        ["DA", format_inr(slip.da), "TDS", format_inr(slip.tds_deduction)],
        ["HRA", format_inr(slip.hra), "Other", format_inr(slip.other_deductions)],
        ["Overtime", format_inr(slip.overtime_amount), "", ""],
    ]
    table = Table(table_data, colWidths=[1.75 * inch, 1.75 * inch, 1.75 * inch, 1.75 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 10))

    net_table = Table([["Net Salary", format_inr(slip.net_salary)]], colWidths=[5.25 * inch, 1.75 * inch])
    net_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GOLD),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
    ]))
    elements.append(net_table)

    elements.append(Spacer(1, 16))
    elements.append(Paragraph(
        "Note: PF/TDS figures reflect what was entered for this slip - this system does not "
        "calculate statutory deductions automatically. Confirm figures with your accountant "
        "before finalizing payroll.", styles["body_secondary"],
    ))

    elements.append(Spacer(1, 24))
    elements.append(Paragraph(build_footer_text(), styles["footer"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_invoice_pdf(order: Order, payments: list[Payment]) -> BytesIO:
    """Client invoice for an order - order value, payment history, and
    balance due. There is no separate GST/line-item model for orders in
    this system (unlike Purchases, which do carry GST), so this reflects
    the order as a single line item plus its actual payment history -
    it does not invent a tax breakdown the data doesn't support."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.6 * inch, bottomMargin=0.7 * inch,
                             leftMargin=0.6 * inch, rightMargin=0.6 * inch)
    styles = get_styles()
    elements = build_header("INVOICE", order.order_code, datetime.utcnow().strftime("%d %b %Y"), order.business_id)

    client_name = order.client.name if order.client else "-"
    client_phone = order.client.phone if order.client else "-"
    client_address = order.site_address or (order.client.address if order.client else "-")

    elements.append(section_table(
        [[("CLIENT", client_name), ("PHONE", client_phone)],
         [("ADDRESS", client_address), ("PROJECT", order.project_type or "-")]],
        [3.5 * inch, 3.5 * inch],
    ))
    elements.append(Spacer(1, 14))

    elements.append(line_items_table(
        ["Description", "Amount"],
        [[order.project_type or "Project", format_inr(order.order_value)]],
        [5 * inch, 2 * inch],
    ))

    if payments:
        elements.append(Spacer(1, 16))
        elements.append(Paragraph("PAYMENT HISTORY", styles["section_label"]))
        elements.append(line_items_table(
            ["Receipt ID", "Date", "Mode", "Reference", "Amount"],
            [[p.business_id or p.receipt_code, _fmt_date(p.date), p.payment_mode,
              p.reference_number or "-", format_inr(p.amount)] for p in payments],
            [1.3 * inch, 1.3 * inch, 1.2 * inch, 1.6 * inch, 1.6 * inch],
        ))

    elements.append(Spacer(1, 16))
    elements.append(line_items_table(
        ["Summary", ""],
        [["Order Value", format_inr(order.order_value)],
         ["Total Received", format_inr(order.total_received)]],
        [5 * inch, 2 * inch],
        totals_rows=[["Balance Due", format_inr(order.balance)]],
    ))

    elements.append(Spacer(1, 24))
    elements.append(Paragraph(build_footer_text(), styles["footer"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer
