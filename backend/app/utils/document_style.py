"""Shared Woodful Creations document design system - used by every PDF
this application generates, so an estimate, an invoice, and a salary
slip all look like they came from the same professional business, not
three unrelated generic reports.

Palette matches the actual application design system (near-black ink,
warm ivory, refined gold) - not the generic reportlab default blue.
"""
import os

from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.platypus import Table, TableStyle, Paragraph, Image, Spacer


def pdf_text(value) -> str:
    """Escapes user-controlled text before it goes into a reportlab
    Paragraph string. Paragraph interprets its content as a limited
    XML/HTML markup subset - unescaped &, <, > in a client name,
    remark, or bank name would either break the parser (crashing PDF
    generation) or, worse, let a user inject fake formatting tags
    (e.g. a name containing "<b>...") into a generated document.
    Always wrap user-supplied text with this before interpolating it
    into an f-string passed to Paragraph()."""
    if value is None:
        return ""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

INK = colors.HexColor("#11110F")
CHARCOAL = colors.HexColor("#1A1916")
IVORY = colors.HexColor("#F6F2EA")
GOLD = colors.HexColor("#C08A45")
BORDER = colors.HexColor("#DED6C8")
TEXT_SECONDARY = colors.HexColor("#70685D")

LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "logo.png")


def format_inr(value) -> str:
    """Indian digit grouping (1,25,000 not 125,000), matching the
    frontend's utils/currency.js exactly, so a figure looks the same
    whether a person sees it in the app or on a printed document."""
    n = float(value or 0)
    negative = n < 0
    n = abs(n)
    whole = int(n)
    paise = round((n - whole) * 100)
    s = str(whole)
    if len(s) <= 3:
        grouped = s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        parts = []
        while len(rest) > 2:
            parts.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.insert(0, rest)
        grouped = ",".join(parts) + "," + last3
    result = f"Rs {grouped}.{paise:02d}"
    return f"-{result}" if negative else result


def get_styles():
    base = getSampleStyleSheet()
    return {
        "doc_title": ParagraphStyle(
            "DocTitle", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=18,
            textColor=INK, spaceAfter=2,
        ),
        "doc_subtitle": ParagraphStyle(
            "DocSubtitle", parent=base["Normal"], fontName="Helvetica", fontSize=9,
            textColor=TEXT_SECONDARY, spaceAfter=0,
        ),
        "section_label": ParagraphStyle(
            "SectionLabel", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8,
            textColor=GOLD, spaceAfter=4, spaceBefore=10,
        ),
        "body": ParagraphStyle(
            "Body", parent=base["Normal"], fontName="Helvetica", fontSize=9.5,
            textColor=INK, leading=14,
        ),
        "body_secondary": ParagraphStyle(
            "BodySecondary", parent=base["Normal"], fontName="Helvetica", fontSize=8.5,
            textColor=TEXT_SECONDARY, leading=13,
        ),
        "total_label": ParagraphStyle(
            "TotalLabel", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=11,
            textColor=colors.white, alignment=TA_RIGHT,
        ),
        "footer": ParagraphStyle(
            "Footer", parent=base["Normal"], fontName="Helvetica", fontSize=7.5,
            textColor=TEXT_SECONDARY, alignment=TA_CENTER,
        ),
    }


def build_header(document_title: str, reference: str, date_label: str, business_id: str = None):
    """Logo + wordmark on the left, document type/reference on the
    right - the same two-sided header pattern used on every document.
    business_id, when supplied, is the opaque 10-character external
    identifier (e.g. A7K92P4XQ1) shown alongside the human-scannable
    reference code - optional since not every document type has one."""
    styles = get_styles()
    elements = []

    if os.path.exists(LOGO_PATH):
        logo = Image(LOGO_PATH, width=1.5 * inch, height=1.5 * inch * (609 / 2435))
    else:
        logo = Paragraph("WOODFUL CREATIONS", styles["doc_title"])

    id_line = f'<br/><font size="7.5" color="#C08A45">ID: {pdf_text(business_id)}</font>' if business_id else ""
    header_table = Table(
        [[logo, Paragraph(
            f'<para align="right"><font size="14" color="#11110F"><b>{pdf_text(document_title)}</b></font><br/>'
            f'<font size="9" color="#70685D">{pdf_text(reference)}</font><br/>'
            f'<font size="9" color="#70685D">{pdf_text(date_label)}</font>{id_line}</para>',
            styles["body"],
        )]],
        colWidths=[3 * inch, 4 * inch],
    )
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 4))
    elements.append(Table([[""]], colWidths=[7 * inch], rowHeights=[1.2],
                           style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), GOLD)])))
    elements.append(Spacer(1, 14))
    return elements


def section_table(rows, col_widths):
    """A clean two-column key/value block (client info, project info,
    etc.) - ivory label backing, no gridlines, not a database table."""
    styles = get_styles()
    data = [[Paragraph(f'<font color="#70685D" size="8">{pdf_text(label)}</font><br/>'
                        f'<font color="#11110F" size="9.5">{pdf_text(value) or "-"}</font>', styles["body"])
             for label, value in row] for row in rows]
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BACKGROUND", (0, 0), (-1, -1), IVORY),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


def line_items_table(header_row, data_rows, col_widths, totals_rows=None):
    """The commercial/line-item table - gold header instead of generic
    accounting blue, ivory zebra striping, gold total row."""
    styles = get_styles()
    table_data = [header_row] + data_rows
    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("GRID", (0, 0), (-1, len(data_rows)), 0.5, BORDER),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
    ]
    for i in range(1, len(data_rows) + 1):
        if i % 2 == 0:
            style_commands.append(("BACKGROUND", (0, i), (-1, i), IVORY))

    if totals_rows:
        start = len(table_data)
        table_data += totals_rows
        for i, row in enumerate(totals_rows):
            row_idx = start + i
            is_grand_total = i == len(totals_rows) - 1
            if is_grand_total:
                style_commands += [
                    ("BACKGROUND", (0, row_idx), (-1, row_idx), GOLD),
                    ("TEXTCOLOR", (0, row_idx), (-1, row_idx), colors.white),
                    ("FONTNAME", (0, row_idx), (-1, row_idx), "Helvetica-Bold"),
                    ("FONTSIZE", (0, row_idx), (-1, row_idx), 11),
                ]
            else:
                style_commands += [
                    ("FONTNAME", (0, row_idx), (-1, row_idx), "Helvetica-Bold"),
                    ("LINEABOVE", (0, row_idx), (-1, row_idx), 0.5, BORDER),
                ]

    t = Table(table_data, colWidths=col_widths)
    t.setStyle(TableStyle(style_commands))
    return t


def build_footer_text(extra_line: str = None) -> str:
    lines = ["Woodful Creations &middot; This is a system-generated document."]
    if extra_line:
        lines.append(extra_line)
    return "<br/>".join(lines)
