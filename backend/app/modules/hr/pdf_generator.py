"""Salary slip PDF generation - reportlab Platypus using the shared
Woodful document design system. Split out of the former
shared/pdf_generator.py - see modules/sales/pdf_generator.py's
docstring for why."""
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

from app.modules.hr.models import SalarySlip, Leave
from app.shared.document_style import (
    format_inr, get_styles,
    INK, BORDER, IVORY, LOGO_PATH, LOGO_ASPECT, pdf_text, fmt_date, mask_value, _contact_block,
)


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
    pan = mask_value(employee.pan) if employee else "-"
    uan = mask_value(employee.uan) if employee else "-"
    tax_regime = (employee.tax_regime if employee else None) or "-"
    bank_name = (employee.bank_name if employee else None) or "-"
    account_number = mask_value(employee.bank_account_number) if employee else "-"
    joining_date = fmt_date(employee.joining_date) if employee else "-"
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


