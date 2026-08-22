"""Order estimate PDF generation (reportlab Platypus), using the shared
Woodful document design system in document_style.py."""
import os
from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.estimate import Estimate
from app.models.client import Client
from app.models.product import Product
from app.models.salary_slip import SalarySlip
from app.models.payment import Payment
from app.models.leave import Leave
from app.utils.document_style import (
    format_inr, get_styles, build_header, section_table, line_items_table, build_footer_text,
    INK, GOLD, BORDER, IVORY, TEXT_SECONDARY, LOGO_PATH, LOGO_ASPECT, pdf_text, _contact_block,
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
    client_id_display = f"{client_name} ({order.client.client_code})" if order.client and order.client.client_code else client_name
    client_phone = _mask_phone(order.client.phone) if order.client else "-"
    client_address = order.site_address or (order.client.address if order.client else "-")
    # Source Estimate where applicable (spec's own explicit requirement) -
    # a direct order genuinely has none, and that's shown plainly as
    # "Direct Order" rather than a blank/missing field.
    source_line = ("SOURCE ESTIMATE", order.source_estimate_code) if order.source_estimate_code else ("SOURCE", "Direct Order")

    elements.append(section_table(
        [[("CLIENT", client_id_display), ("PHONE", client_phone)],
         [("PROJECT TYPE", order.project_type or "-"), ("DELIVERY DATE", _fmt_date(order.delivery_date))],
         [("SITE ADDRESS", client_address), ("STATUS", f"{order.project_status} ({order.progress_percent}% complete)")],
         [source_line, ("PAYMENT", order.payment_status)]],
        [3.5 * inch, 3.5 * inch],
    ))
    elements.append(Spacer(1, 14))

    if order.items:
        item_rows = [
            [Paragraph(pdf_text(f"{item.product_code} - {item.description}" if item.product_id else item.description), styles["table_cell"]),
             item.category or "-", f"{float(item.quantity):g}", item.unit or "-",
             format_inr(item.rate), format_inr(item.amount)]
            for item in order.items
        ]
        subtotal = order.items_subtotal
        totals_rows = [["Subtotal", "", "", "", "", format_inr(subtotal)]]
        if order.discount:
            totals_rows.append(["Discount", "", "", "", "", f"-{format_inr(order.discount)}"])
        totals_rows.append([f"GST ({float(order.tax_percent)}%)", "", "", "", "", format_inr(order.tax_amount)])
        totals_rows.append(["Grand Total", "", "", "", "", format_inr(order.order_value)])
        elements.append(line_items_table(
            ["Description", "Category", "Qty", "Unit", "Rate", "Amount"],
            item_rows,
            [2.1 * inch, 0.85 * inch, 0.55 * inch, 0.65 * inch, 1.2 * inch, 1.65 * inch],
            totals_rows=totals_rows,
        ))
    else:
        # Legacy fallback for an order created before line items existed
        # (a bare order_value with no itemized scope) - still identifies
        # this honestly as "no itemized scope recorded" rather than
        # silently showing nothing.
        elements.append(line_items_table(
            ["Description", "Amount"],
            [["Order Value (no itemized scope on record)", format_inr(order.order_value)]],
            [5 * inch, 2 * inch],
            totals_rows=[["Grand Total", format_inr(order.order_value)]],
        ))

    elements.append(Spacer(1, 14))
    elements.append(line_items_table(
        ["Payment Summary", "Amount"],
        [
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
        elements.append(Paragraph(f'<font color="#70685D" size="8">REMARKS</font><br/>{pdf_text(order.remarks)}', styles["body"]))

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
    client_id_display = f"{client_name} ({estimate.client.client_code})" if estimate.client and estimate.client.client_code else client_name
    client_phone = _mask_phone(estimate.client.phone) if estimate.client else "-"
    client_address = estimate.client.address if estimate.client else "-"

    # Only surface version info when this is genuinely part of a
    # revision chain - v1 with no revisions carries no information and
    # is just noise on every ordinary estimate.
    is_revision = estimate.version > 1 or estimate.parent_estimate_id is not None
    row2_right = ("VERSION", f"v{estimate.version}") if is_revision else ("SCOPE", estimate.description or "-")

    elements.append(section_table(
        [[("CLIENT", client_id_display), ("PHONE", client_phone)],
         [("VALID UNTIL *", _fmt_date(estimate.valid_until)), row2_right],
         [("ADDRESS", client_address), ("SCOPE", estimate.description or "-") if is_revision else ("STATUS", estimate.status.title())]],
        [3.5 * inch, 3.5 * inch],
        title="CLIENT & ESTIMATE DETAILS",
    ))
    elements.append(Spacer(1, 14))

    if estimate.line_items:
        item_rows = [
            [Paragraph(pdf_text(f"{item.product_code} - {item.description}" if item.product_id else item.description), styles["table_cell"]),
             item.category or "-", f"{float(item.quantity):g}", item.unit or "-",
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
            [2.1 * inch, 0.85 * inch, 0.55 * inch, 0.65 * inch, 1.2 * inch, 1.65 * inch],
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

    if estimate.remarks:
        elements.append(Spacer(1, 14))
        elements.append(Paragraph(f'<font color="#70685D" size="8">REMARKS</font><br/>{pdf_text(estimate.remarks)}', styles["body"]))

    elements.append(Spacer(1, 18))
    elements.append(Paragraph(
        '* As per agreed schedule. This estimate is valid until the date marked above; '
        'prices may change after expiry.',
        ParagraphStyle("TermsNote", parent=styles["body_secondary"], alignment=TA_LEFT),
    ))

    elements.append(Spacer(1, 24))
    elements.append(Paragraph(build_footer_text(), styles["footer"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_client_pdf(client: Client) -> BytesIO:
    """Client profile/summary document (Family 103 section 6) - contact
    information plus a real sales summary derived from the client's
    actual Orders (Family 103: "only include information that is
    actually supported by the current codebase" - no fabricated
    relationships). Uses the same Woodful document header/footer as
    every other generated PDF."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.6 * inch, bottomMargin=0.7 * inch,
                             leftMargin=0.6 * inch, rightMargin=0.6 * inch)
    styles = get_styles()
    elements = build_header("CLIENT PROFILE", client.client_code, datetime.utcnow().strftime("%d %b %Y"), client.business_id)

    contact_row = [("CONTACT PERSON", client.contact_person or "-"), ("PHONE", _mask_phone(client.phone))]
    if client.alternate_phone:
        contact_row = [("CONTACT PERSON", client.contact_person or "-"), ("ALTERNATE PHONE", _mask_phone(client.alternate_phone))]
    elements.append(section_table(
        [contact_row,
         [("EMAIL", client.email or "-"), ("CITY", client.city or "-")],
         [("ADDRESS", client.address or "-"), ("SITE ADDRESS", client.site_address or "-")],
         [("GSTIN", client.gstin or "-"), ("STATUS", client.status)],
         [("LEAD SOURCE", client.lead_source or "-"), ("CLIENT SINCE", _fmt_date(client.created_at))]],
        [3.5 * inch, 3.5 * inch],
    ))
    elements.append(Spacer(1, 16))

    orders = client.orders or []
    if orders:
        total_value = sum(float(o.order_value or 0) for o in orders)
        total_received = sum(float(o.total_received or 0) for o in orders)
        outstanding = sum(float(o.balance or 0) for o in orders)
        elements.append(Paragraph("SALES SUMMARY", styles["section_label"]))
        elements.append(line_items_table(
            ["Metric", "Value"],
            [["Total Orders", str(len(orders))],
             ["Total Order Value", format_inr(total_value)],
             ["Total Received", format_inr(total_received)],
             ["Outstanding Balance", format_inr(outstanding)]],
            [5 * inch, 2 * inch],
        ))
        elements.append(Spacer(1, 14))
        elements.append(Paragraph("ORDER HISTORY", styles["section_label"]))
        elements.append(line_items_table(
            ["Order", "Date", "Status", "Value"],
            [[o.order_code, _fmt_date(o.order_date), o.project_status, format_inr(o.order_value)]
             for o in sorted(orders, key=lambda o: o.order_date or datetime.min, reverse=True)],
            [1.6 * inch, 1.6 * inch, 2 * inch, 1.8 * inch],
        ))
    else:
        elements.append(Paragraph(
            '<font color="#70685D" size="9">No orders yet.</font>', styles["body"],
        ))

    if client.remarks:
        elements.append(Spacer(1, 14))
        elements.append(Paragraph(f'<font color="#70685D" size="8">NOTES</font><br/>{pdf_text(client.remarks)}', styles["body"]))

    elements.append(Spacer(1, 24))
    elements.append(Paragraph(build_footer_text(), styles["footer"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_product_pdf(product: Product) -> BytesIO:
    """Product Master detail document (Family 104 section 40)."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.6 * inch, bottomMargin=0.7 * inch,
                             leftMargin=0.6 * inch, rightMargin=0.6 * inch)
    styles = get_styles()
    elements = build_header("PRODUCT", product.product_code, datetime.utcnow().strftime("%d %b %Y"), product.business_id)

    dims = "-"
    if product.length and product.width and product.height:
        dims = f"{product.length}\u00d7{product.width}\u00d7{product.height} {product.dimension_unit or ''}".strip()

    elements.append(section_table(
        [[("PRODUCT NAME", product.name), ("TYPE", product.product_type.title())],
         [("CATEGORY", product.category or "-"), ("SUBCATEGORY", product.subcategory or "-")],
         [("UNIT", product.unit), ("DIMENSIONS", dims)],
         [("PRIMARY MATERIAL", product.primary_material or "-"), ("FINISH", product.finish or "-")],
         [("DEFAULT RATE", format_inr(product.selling_price) if product.selling_price is not None else "-"),
          ("GST %", f"{float(product.gst_percent)}%" if product.gst_percent is not None else "-")],
         [("STATUS", "Active" if product.is_active else "Inactive"), ("", "")]],
        [3.5 * inch, 3.5 * inch],
    ))

    if product.specifications:
        elements.append(Spacer(1, 14))
        elements.append(Paragraph(
            f'<font color="#70685D" size="8">DESCRIPTION / SPECIFICATIONS</font><br/>{pdf_text(product.specifications)}',
            styles["body"],
        ))

    if product.notes:
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(f'<font color="#70685D" size="8">NOTES</font><br/>{pdf_text(product.notes)}', styles["body"]))

    elements.append(Spacer(1, 24))
    elements.append(Paragraph(build_footer_text(), styles["footer"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer


def _mask(value, keep_last=4):
    """XXXXXXXXX1560 style masking for PAN/UAN/account numbers - shows
    only the last few characters, matching the reference's masked
    fields. Never shown in full, even on the employee's own slip -
    masking on a printed/downloadable document is a baseline practice
    regardless of who's viewing it."""
    if not value:
        return "-"
    value = str(value)
    if len(value) <= keep_last:
        return "X" * len(value)
    return "X" * (len(value) - keep_last) + value[-keep_last:]


def _mask_phone(value):
    """98XXXXXX10 style masking for client phone numbers on
    customer-facing PDFs - first 2 and last 2 digits visible, middle
    masked. A different convention from _mask() above (which shows only
    a tail) - phone numbers use this head+tail pattern specifically per
    the approved Woodful privacy requirement. The complete number
    always remains in the database and visible to authorized users
    inside the application; this only affects what's printed on a
    document that could leave the building."""
    if not value:
        return "-"
    value = str(value)
    if len(value) <= 4:
        return "X" * len(value)
    return value[:2] + "X" * (len(value) - 4) + value[-2:]


def _leave_summary(db: Session, employee_id: int, year: str):
    """Days used per leave type this calendar year, from real Approved
    Leave records - this system tracks individual leave requests, not
    an allotted running balance, so "days used" is the honest figure
    to show rather than fabricating a remaining-balance number the
    data doesn't support."""
    if not employee_id:
        return {}
    try:
        target_year = int(year)
    except (TypeError, ValueError):
        target_year = datetime.utcnow().year
    records = db.query(Leave).filter(
        Leave.employee_id == employee_id, Leave.status == "Approved",
    ).all()
    summary = {}
    for r in records:
        if r.start_date and r.start_date.year == target_year:
            summary[r.leave_type] = summary.get(r.leave_type, 0) + float(r.days or 0)
    return summary


def generate_salary_slip_pdf(slip: SalarySlip, db: Session) -> BytesIO:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.55 * inch, bottomMargin=0.5 * inch,
                             leftMargin=0.55 * inch, rightMargin=0.55 * inch)
    styles = get_styles()
    elements = []

    employee = slip.employee
    employee_name = employee.name if employee else "-"
    employee_code = employee.employee_code if employee else "-"

    # Header: logo top-left, Woodful contact details top-right -
    # matching the approved Woodful visual template. Logo size and the
    # contact block (all four lines with icons, including the phone
    # line - the reference's own masked placeholder, reproduced
    # verbatim) were corrected against the actual reference; see the
    # detailed rationale on build_header() in document_style.py, which
    # this duplicates rather than calls because the payslip's title
    # block (Payslip / MAY 2026 / Employee Name bar) has a different
    # shape than every other document's title+reference/date row.
    if os.path.exists(LOGO_PATH):
        logo = Image(LOGO_PATH, width=2.7 * inch, height=2.7 * inch * LOGO_ASPECT)
        logo.hAlign = "LEFT"
    else:
        logo = Paragraph("WOODFUL CREATIONS", styles["doc_title"])
    top_row = Table([[logo, _contact_block()]], colWidths=[4 * inch, 3.4 * inch])
    top_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(top_row)
    elements.append(Spacer(1, 4))
    elements.append(Table([[""]], colWidths=[7.4 * inch], rowHeights=[0.75],
                           style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), INK)])))
    elements.append(Spacer(1, 6))

    title_style = ParagraphStyle("PayslipTitle", parent=styles["doc_title"], fontSize=20, spaceAfter=0, leading=24)
    period_style = ParagraphStyle("PayslipPeriod", parent=styles["doc_title"], fontSize=13, spaceAfter=6, leading=16)
    elements.append(Paragraph("Payslip", title_style))
    elements.append(Paragraph(f"{slip.month.upper()} {slip.year}", period_style))

    name_style = ParagraphStyle("EmployeeNameLabel", parent=styles["body"], fontSize=10)
    name_table = Table(
        [[Paragraph(f'<b>Employee Name</b> &nbsp;&nbsp;:&nbsp;&nbsp; {pdf_text(employee_name)}', name_style)]],
        colWidths=[7.4 * inch],
    )
    name_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), IVORY),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(name_table)
    elements.append(Spacer(1, 8))

    # Three-column info block: Employee / Payment & Leave / Employment.
    pan = _mask(employee.pan) if employee else "-"
    uan = _mask(employee.uan) if employee else "-"
    tax_regime = (employee.tax_regime if employee else None) or "-"
    bank_name = (employee.bank_name if employee else None) or "-"
    account_number = _mask(employee.bank_account_number) if employee else "-"
    joining_date = _fmt_date(employee.joining_date) if employee else "-"
    designation = (employee.designation if employee else None) or "-"
    department = (employee.department if employee else None) or "-"

    leave_totals = _leave_summary(db, employee.id if employee else None, slip.year)

    def _field(label, value):
        return Paragraph(f'<font color="#70685D" size="8">{label}</font><br/>'
                          f'<font color="#3B1400" size="9.5">{pdf_text(value)}</font>', styles["body"])

    def _header_cell(text):
        return Paragraph(f'<font color="#FFFFFF" size="8.5"><b>{text}</b></font>', styles["body"])

    info_rows = [
        [_header_cell("EMPLOYEE INFORMATION"), _header_cell("PAYMENT &amp; LEAVE INFORMATION"), _header_cell("EMPLOYMENT INFORMATION")],
        [_field("Emp. No.", employee_code), _field("Bank Name", bank_name), _field("Date of Joining", joining_date)],
        [_field("PAN", pan), _field("Acc. No.", account_number), _field("Designation", designation)],
        [_field("UAN", uan), _field("Days Paid", str(slip.paid_days)), _field("Department", department)],
        [_field("Tax Regime", tax_regime),
         _field("Leave Balance", ", ".join(f"{k}: {v:g}" for k, v in leave_totals.items()) or "No leave taken this year"),
         ""],
    ]
    info_table = Table(info_rows, colWidths=[2.47 * inch, 2.47 * inch, 2.46 * inch])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, 0), 4), ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
        ("TOPPADDING", (0, 1), (-1, -1), 4), ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 8))

    # Earnings (+ Arrears, structurally shown even though this system
    # doesn't track arrears separately from the current-month figure -
    # honestly "-" rather than fabricated) and Deductions, side by side
    # in one 5-column table so the header rows line up.
    earnings_rows = [
        ("Basic", slip.basic), ("Dearness Allowance", slip.da),
        ("House Rent Allowance", slip.hra), ("Overtime", slip.overtime_amount),
    ]
    earnings_rows = [(label, amt) for label, amt in earnings_rows if float(amt or 0) != 0] or [("Basic", slip.basic)]
    deduction_rows = [
        ("Provident Fund", slip.pf_deduction), ("Tax Deducted at Source", slip.tds_deduction),
        ("Other Deductions", slip.other_deductions),
    ]
    deduction_rows = [(label, amt) for label, amt in deduction_rows if float(amt or 0) != 0]

    row_count = max(len(earnings_rows), len(deduction_rows), 1)
    table_rows = [["EARNINGS", "CURRENT (INR)", "ARREARS (INR)", "DEDUCTIONS", "AMOUNT (INR)"]]
    for i in range(row_count):
        e_label, e_amt = earnings_rows[i] if i < len(earnings_rows) else ("", None)
        d_label, d_amt = deduction_rows[i] if i < len(deduction_rows) else ("", None)
        table_rows.append([
            e_label, format_inr(e_amt) if e_amt is not None else "", "-" if e_label else "",
            d_label, format_inr(d_amt) if d_amt is not None else "",
        ])
    total_earnings = sum(float(amt or 0) for _, amt in earnings_rows)
    total_deductions = sum(float(amt or 0) for _, amt in deduction_rows)
    table_rows.append([
        "TOTAL EARNINGS (Current + Arrears)", format_inr(total_earnings), "",
        "TOTAL DEDUCTIONS", format_inr(total_deductions),
    ])

    pay_table = Table(table_rows, colWidths=[1.9 * inch, 1.15 * inch, 1.05 * inch, 1.9 * inch, 1.4 * inch])
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), INK), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("ALIGN", (1, 0), (2, -1), "RIGHT"), ("ALIGN", (4, 0), (4, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -2), 0.5, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("BACKGROUND", (0, -1), (-1, -1), IVORY),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.75, INK),
        ("SPAN", (0, -1), (1, -1)),
    ]
    pay_table.setStyle(TableStyle(style_cmds))
    elements.append(pay_table)
    elements.append(Spacer(1, 8))

    net_pay_style = ParagraphStyle("NetPayLabel", parent=styles["body"], fontSize=10.5, textColor=colors.white)
    net_pay_value_style = ParagraphStyle("NetPayValue", parent=styles["body"], fontSize=13,
                                          textColor=INK, alignment=TA_RIGHT, fontName="Helvetica-Bold")
    net_table = Table(
        [[Paragraph("<b>NET PAY (INR)</b>", net_pay_style), Paragraph(format_inr(slip.net_salary), net_pay_value_style)]],
        colWidths=[5.1 * inch, 2.3 * inch],
    )
    net_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), INK),
        ("BACKGROUND", (1, 0), (1, 0), IVORY),
        ("BOX", (0, 0), (-1, -1), 0.75, INK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(net_table)
    elements.append(Spacer(1, 8))

    # Projected tax information. Annual Income is a real derivation
    # (basic+da+hra+overtime, annualized) from this slip's own stored
    # figures. The remaining fields need an actual Indian tax-slab
    # engine this system does not have, so they show "-" rather than a
    # fabricated number - honest about what is and isn't computed here.
    monthly_gross = float(slip.basic or 0) + float(slip.da or 0) + float(slip.hra or 0) + float(slip.overtime_amount or 0)
    annual_income = monthly_gross * 12

    tax_header = Table([[_header_cell("TAX INFORMATION (Projected)")]], colWidths=[7.4 * inch])
    tax_header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), INK),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.append(tax_header)

    tax_rows = [
        [_field("Annual Income*", format_inr(annual_income)), _field("Net Taxable Income", "-"), ""],
        [_field("Deductions u/s 16", "-"), _field("Total Tax Payable", "-"), ""],
        [_field("Chapter VIA Relief", "-"), _field("Tax Deducted till date", "-"), ""],
        ["", _field("Balance Tax", "-"), ""],
    ]
    tax_table = Table(tax_rows, colWidths=[2.47 * inch, 2.47 * inch, 2.46 * inch])
    tax_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
    ]))
    elements.append(tax_table)
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(
        "* Please note, annual income is a projection based on this month's earnings and does not "
        "reflect a full statutory tax computation. Confirm actual liability with your accountant.",
        styles["body_secondary"],
    ))

    # Generous whitespace for physical signing - no box, no fabricated
    # signature image, matching the reference's spacious lower section.
    elements.append(Spacer(1, 14))

    timestamp = datetime.utcnow().strftime("%d %b %Y, %H:%M:%S")
    sign_style_right = ParagraphStyle("SignRight", parent=styles["body"], fontSize=9.5, alignment=TA_RIGHT)
    sign_style_left = ParagraphStyle("SignLeft", parent=styles["body_secondary"], fontSize=8, alignment=TA_LEFT)
    footer_row = Table(
        [[
            Paragraph(f"Payslip generated on: {timestamp}", sign_style_left),
            Paragraph('<font color="#3B1400" size="11"><b>Nikhil Soni</b></font><br/>'
                      '<font color="#70685D" size="9">Chief Executive Officer</font><br/>'
                      '<font color="#70685D" size="9">Woodful Creations</font>', sign_style_right),
        ]],
        colWidths=[3.7 * inch, 3.7 * inch],
    )
    footer_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(footer_row)

    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_invoice_pdf(order: Order, payments: list[Payment]) -> BytesIO:
    """Client invoice for an order - order value, payment history, and
    balance due. Shows the order's actual line items (with real Product
    references and discount/GST, added alongside Product Master) when
    they exist; falls back to a single flat line only for older/bare
    orders that predate itemization, the same legacy-fallback pattern
    generate_estimate_pdf already uses."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.6 * inch, bottomMargin=0.7 * inch,
                             leftMargin=0.6 * inch, rightMargin=0.6 * inch)
    styles = get_styles()
    elements = build_header("INVOICE", order.order_code, datetime.utcnow().strftime("%d %b %Y"), order.business_id)

    client_name = order.client.name if order.client else "-"
    client_id_display = f"{client_name} ({order.client.client_code})" if order.client and order.client.client_code else client_name
    client_phone = _mask_phone(order.client.phone) if order.client else "-"
    client_address = order.site_address or (order.client.address if order.client else "-")

    elements.append(section_table(
        [[("CLIENT", client_id_display), ("PHONE", client_phone)],
         [("ADDRESS", client_address), ("PROJECT", order.project_type or "-")]],
        [3.5 * inch, 3.5 * inch],
    ))
    elements.append(Spacer(1, 14))

    if order.items:
        item_rows = [
            [Paragraph(pdf_text(f"{item.product_code} - {item.description}" if item.product_id else item.description), styles["table_cell"]),
             f"{float(item.quantity):g}", item.unit or "-", format_inr(item.rate), format_inr(item.amount)]
            for item in order.items
        ]
        totals_rows = []
        if order.items_subtotal is not None:
            totals_rows.append(["Subtotal", "", "", "", format_inr(order.items_subtotal)])
        if order.discount:
            totals_rows.append(["Discount", "", "", "", f"-{format_inr(order.discount)}"])
        if order.tax_amount:
            totals_rows.append([f"GST ({float(order.tax_percent or 0)}%)", "", "", "", format_inr(order.tax_amount)])
        totals_rows.append(["Grand Total", "", "", "", format_inr(order.order_value)])
        elements.append(line_items_table(
            ["Description", "Qty", "Unit", "Rate", "Amount"],
            item_rows,
            [2.85 * inch, 0.65 * inch, 0.85 * inch, 1.2 * inch, 1.45 * inch],
            totals_rows=totals_rows,
        ))
    else:
        # Legacy fallback for orders created before itemization existed.
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
