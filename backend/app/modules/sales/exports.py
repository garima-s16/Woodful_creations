"""Sales-domain PDF generation (order estimate, estimate, invoice) -
reportlab Platypus using the shared Woodful document design system.
Split out of the former shared/pdf_generator.py, which mixed every
domain's document layouts together under shared/ (meant to stay
business-neutral - a domain-specific RBAC/field-choice-laden PDF
generator is not that)."""
from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from app.modules.sales.models import Order, Estimate, Payment
from app.shared import (
    format_inr, get_styles, build_header, section_table, line_items_table, build_footer_text,
    pdf_text, fmt_date, mask_phone,
)


def generate_order_estimate_pdf(order: Order) -> BytesIO:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.6 * inch, bottomMargin=0.7 * inch,
                             leftMargin=0.6 * inch, rightMargin=0.6 * inch)
    styles = get_styles()
    elements = build_header("ORDER SUMMARY", order.order_code, fmt_date(order.order_date), order.business_id)

    client_name = order.client.name if order.client else "-"
    client_id_display = f"{client_name} ({order.client.client_code})" if order.client and order.client.client_code else client_name
    client_phone = mask_phone(order.client.phone) if order.client else "-"
    client_address = order.site_address or (order.client.address if order.client else "-")
    # Source Estimate where applicable (spec's own explicit requirement) -
    # a direct order genuinely has none, and that's shown plainly as
    # "Direct Order" rather than a blank/missing field.
    source_line = ("SOURCE ESTIMATE", order.source_estimate_code) if order.source_estimate_code else ("SOURCE", "Direct Order")

    elements.append(section_table(
        [[("CLIENT", client_id_display), ("PHONE", client_phone)],
         [("PROJECT TYPE", order.project_type or "-"), ("DELIVERY DATE", fmt_date(order.delivery_date))],
         [("STATUS", f"{order.project_status} ({order.progress_percent}% complete)"), ("SITE ADDRESS", client_address)],
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
    elements = build_header("ESTIMATE", estimate.estimate_code, fmt_date(estimate.created_at), estimate.business_id)

    client_name = estimate.client.name if estimate.client else "-"
    client_id_display = f"{client_name} ({estimate.client.client_code})" if estimate.client and estimate.client.client_code else client_name
    client_phone = mask_phone(estimate.client.phone) if estimate.client else "-"
    client_address = estimate.client.address if estimate.client else "-"

    # Only surface version info when this is genuinely part of a
    # revision chain - v1 with no revisions carries no information and
    # is just noise on every ordinary estimate.
    is_revision = estimate.version > 1 or estimate.parent_estimate_id is not None
    row2_right = ("VERSION", f"v{estimate.version}") if is_revision else ("SCOPE", estimate.description or "-")

    elements.append(section_table(
        [[("CLIENT", client_id_display), ("PHONE", client_phone)],
         [("VALID UNTIL *", fmt_date(estimate.valid_until)), row2_right],
         [("SCOPE", estimate.description or "-") if is_revision else ("STATUS", estimate.status.title()), ("ADDRESS", client_address)]],
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
    client_phone = mask_phone(order.client.phone) if order.client else "-"
    client_address = order.site_address or (order.client.address if order.client else "-")

    elements.append(section_table(
        [[("CLIENT", client_id_display), ("PHONE", client_phone)],
         [("PROJECT", order.project_type or "-"), ("ADDRESS", client_address)]],
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
            [[p.business_id or p.receipt_code, fmt_date(p.date), p.payment_mode,
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
