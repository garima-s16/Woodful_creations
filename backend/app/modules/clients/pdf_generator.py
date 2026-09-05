"""Client profile PDF generation - reportlab Platypus using the shared
Woodful document design system. Split out of the former
shared/pdf_generator.py - see modules/sales/pdf_generator.py's
docstring for why."""
from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from app.modules.clients.models import Client
from app.shared.document_style import (
    format_inr, get_styles, build_header, section_table, line_items_table, build_footer_text,
    pdf_text, fmt_date, mask_phone,
)


def generate_client_pdf(client: Client, is_privileged: bool) -> BytesIO:
    """Client profile/summary document - contact
    information plus a real sales summary derived from the client's
    actual Orders - only real information actually
    supported by the current codebase, no fabricated
    relationships. Uses the same Woodful document header/footer as
    every other generated PDF.

    Financial figures (order values, received amounts, balances) are
    genuinely gated by is_privileged - previously this function had no
    way to know who was requesting the PDF, so it always printed the
    full sales summary and per-order values regardless of role,
    bypassing the same redaction the normal JSON client API already
    applies for non-master users."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.6 * inch, bottomMargin=0.7 * inch,
                             leftMargin=0.6 * inch, rightMargin=0.6 * inch)
    styles = get_styles()
    elements = build_header("CLIENT PROFILE", client.client_code, datetime.utcnow().strftime("%d %b %Y"), client.business_id)

    contact_row = [("CONTACT PERSON", client.contact_person or "-"), ("PHONE", mask_phone(client.phone))]
    if client.alternate_phone:
        contact_row = [("CONTACT PERSON", client.contact_person or "-"), ("ALTERNATE PHONE", mask_phone(client.alternate_phone))]
    elements.append(section_table(
        [contact_row,
         [("EMAIL", client.email or "-"), ("CITY", client.city or "-")],
         [("ADDRESS", client.address or "-"), ("SITE ADDRESS", client.site_address or "-")],
         [("GSTIN", client.gstin or "-"), ("STATUS", client.status)],
         [("LEAD SOURCE", client.lead_source or "-"), ("CLIENT SINCE", fmt_date(client.created_at))]],
        [3.5 * inch, 3.5 * inch],
    ))
    elements.append(Spacer(1, 16))

    orders = client.orders or []
    if orders:
        if is_privileged:
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
        if is_privileged:
            elements.append(line_items_table(
                ["Order", "Date", "Status", "Value"],
                [[o.order_code, fmt_date(o.order_date), o.project_status, format_inr(o.order_value)]
                 for o in sorted(orders, key=lambda o: o.order_date or datetime.min, reverse=True)],
                [1.6 * inch, 1.6 * inch, 2 * inch, 1.8 * inch],
            ))
        else:
            elements.append(line_items_table(
                ["Order", "Date", "Status"],
                [[o.order_code, fmt_date(o.order_date), o.project_status]
                 for o in sorted(orders, key=lambda o: o.order_date or datetime.min, reverse=True)],
                [2.4 * inch, 2.4 * inch, 2.4 * inch],
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


