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
from reportlab.graphics.shapes import Drawing, Circle, Rect, Polygon


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

# INK was previously #11110F (near-black) - color-sampled directly
# against the actual approved Woodful letterhead reference (the May
# 2026 payslip sample), which uses a warm dark brown/mahogany for
# every section header bar, the document title, and the icon accents,
# never true black. Sampled consistently at #3D1500/#3A1400/#3F1500
# across multiple header bars in that reference; #3B1400 is the
# rounded, single value used everywhere INK is referenced, so every
# document type (estimate, invoice, order summary, payslip) picks up
# the correct brand color from this one constant.
INK = colors.HexColor("#3B1400")
CHARCOAL = colors.HexColor("#1A1916")
IVORY = colors.HexColor("#F6F2EA")
GOLD = colors.HexColor("#C08A45")
BORDER = colors.HexColor("#DED6C8")
TEXT_SECONDARY = colors.HexColor("#70685D")

LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "logo.png")
LOGO_ASPECT = 609 / 2435  # native pixel dimensions of assets/logo.png


def _icon_pin(size=9):
    """Location pin - a circle sitting on a downward point, the same
    silhouette used in the approved letterhead's contact block. Drawn
    as vector shapes (reportlab's base fonts have no pin/phone/
    envelope/camera glyphs to fall back on), colored to match INK."""
    d = Drawing(size, size)
    cx = size / 2
    d.add(Polygon(points=[cx - size * 0.28, size * 0.42, cx + size * 0.28, size * 0.42, cx, 0], fillColor=INK, strokeColor=None))
    d.add(Circle(cx, size * 0.62, size * 0.38, fillColor=INK, strokeColor=None))
    d.add(Circle(cx, size * 0.62, size * 0.15, fillColor=colors.white, strokeColor=None))
    return d


def _icon_phone(size=9):
    """Simple rounded handset body - the pragmatic simplification a
    small monochrome print icon needs at 9pt, rather than attempting a
    literally accurate handset silhouette with reportlab's basic
    shape primitives."""
    d = Drawing(size, size)
    d.add(Rect(size * 0.22, size * 0.02, size * 0.56, size * 0.96, size * 0.22, size * 0.22, fillColor=INK, strokeColor=None))
    return d


def _icon_envelope(size=9):
    """Envelope: an outlined rectangle with a V-fold drawn on top in
    the page's background color, matching a standard mail glyph."""
    d = Drawing(size, size * 0.72)
    h = size * 0.72
    d.add(Rect(0, 0, size, h, fillColor=INK, strokeColor=None))
    d.add(Polygon(points=[size * 0.08, h * 0.85, size / 2, h * 0.35, size * 0.92, h * 0.85], fillColor=colors.white, strokeColor=None))
    return d


def _icon_instagram(size=9):
    """Rounded-square camera outline with a center ring and a small
    corner dot - the recognizable Instagram glyph shape, drawn flat/
    monochrome to match the other print icons rather than reproducing
    the brand's actual multicolor logo."""
    d = Drawing(size, size)
    d.add(Rect(0, 0, size, size, size * 0.28, size * 0.28, fillColor=None, strokeColor=INK, strokeWidth=size * 0.11))
    d.add(Circle(size / 2, size / 2, size * 0.26, fillColor=None, strokeColor=INK, strokeWidth=size * 0.11))
    d.add(Circle(size * 0.78, size * 0.78, size * 0.07, fillColor=INK, strokeColor=None))
    return d


def _contact_block(phone: str = "+91 XXXXX XXXXX"):
    """Icon + text, one row per contact line, right-aligned as a block
    - matching the approved letterhead's top-right panel exactly
    (location, phone, email, Instagram, in that order). phone defaults
    to the masked placeholder shown in the approved reference itself
    (Woodful's real business number isn't available to put here, and
    the reference's OWN letterhead shows it masked this way - this
    isn't per-record masking, it's copying the template verbatim)."""
    styles = get_styles()
    line_style = ParagraphStyle("HeaderContactLine", parent=styles["body"], fontSize=8.5, leading=11, textColor=TEXT_SECONDARY)
    rows = [
        (_icon_pin(), "Indore, Madhya Pradesh, India"),
        (_icon_phone(), phone),
        (_icon_envelope(), "woodfulcreations@gmail.com"),
        (_icon_instagram(), "@woodful_creations"),
    ]
    data = [[icon, Paragraph(pdf_text(text), line_style)] for icon, text in rows]
    t = Table(data, colWidths=[14, 2.1 * inch])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, -1), "RIGHT"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (0, -1), 6),
    ]))
    return t


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
        "table_cell": ParagraphStyle(
            "TableCell", parent=base["Normal"], fontName="Helvetica", fontSize=9,
            textColor=INK, leading=11.5,
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
    """Logo on the left, Woodful contact details on the right (top
    row) - matching the approved Woodful visual template - then a thin
    brand-colored rule, then the document title with its reference/
    date below that, sized close to the title itself so the right side
    doesn't look sparse next to a bold heading.

    business_id is accepted but deliberately NOT rendered right now -
    the human-readable reference code (e.g. EST-009) is treated as
    sufficient traceability on its own for the moment. Kept as a
    parameter (not removed) so re-enabling it later, if ever genuinely
    needed, doesn't require touching every call site again.

    Logo size and the contact block (all four lines - location, phone,
    email, Instagram - each with its icon, right-aligned) were
    corrected against the approved letterhead reference: the logo was
    previously 1.5in wide, well under the ~2.7in the reference actually
    uses, and the phone line was previously omitted rather than
    reproducing the reference's own masked placeholder
    ("+91 XXXXX XXXXX") verbatim. The divider was previously a thick
    solid GOLD bar; the reference has no such bar, just a hairline
    rule, so this now draws a 0.75pt INK-colored line instead."""
    styles = get_styles()
    elements = []

    if os.path.exists(LOGO_PATH):
        logo = Image(LOGO_PATH, width=2.7 * inch, height=2.7 * inch * LOGO_ASPECT)
    else:
        logo = Paragraph("WOODFUL CREATIONS", styles["doc_title"])

    top_row = Table([[logo, _contact_block()]], colWidths=[3.6 * inch, 3.4 * inch])
    top_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(top_row)
    elements.append(Spacer(1, 6))
    elements.append(Table([[""]], colWidths=[7 * inch], rowHeights=[0.75],
                           style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), INK)])))
    elements.append(Spacer(1, 10))

    title_row = Table(
        [[Paragraph(f'<font size="15" color="#3B1400"><b>{pdf_text(document_title)}</b></font>', styles["body"]),
          Paragraph(
              f'<para align="right">'
              f'<font size="12" color="#70685D"><b>{pdf_text(reference)}</b></font><br/>'
              f'<font size="12" color="#70685D">{pdf_text(date_label)}</font></para>',
              styles["body"],
          )]],
        colWidths=[3 * inch, 4 * inch],
    )
    title_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(title_row)
    elements.append(Spacer(1, 10))
    return elements


def section_table(rows, col_widths, title=None):
    """A clean two-column key/value block (client info, project info,
    etc.) - ivory label backing, no gridlines, not a database table.

    title, when supplied, prepends a bold dark header bar naming the
    section - matching the payslip's own "EMPLOYEE INFORMATION" /
    "PAYMENT & LEAVE INFORMATION" convention exactly (same INK
    background, white bold 8.5pt text). Optional and off by default,
    so every existing call site renders identically to before."""
    styles = get_styles()
    data = [[Paragraph(f'<font color="#70685D" size="8">{pdf_text(label)}</font><br/>'
                        f'<font color="#3B1400" size="9.5">{pdf_text(value) or "-"}</font>', styles["body"])
             for label, value in row] for row in rows]
    style_commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BACKGROUND", (0, 0), (-1, -1), IVORY),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]
    if title:
        title_cell = Paragraph(f'<font color="#FFFFFF" size="8.5"><b>{pdf_text(title)}</b></font>', styles["body"])
        span_width = sum(col_widths)
        data = [[title_cell] + [""] * (len(col_widths) - 1)] + data
        style_commands += [
            ("SPAN", (0, 0), (-1, 0)),
            ("BACKGROUND", (0, 0), (-1, 0), INK),
            ("TOPPADDING", (0, 0), (-1, 0), 4), ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
        ]
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle(style_commands))
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

    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle(style_commands))
    return t


def build_footer_text(extra_line: str = None) -> str:
    lines = ["Woodful Creations &middot; This is a system-generated document."]
    if extra_line:
        lines.append(extra_line)
    return "<br/>".join(lines)

# ===========================================================================
# Generic formatting/redaction primitives shared across every domain's PDF
# generator (moved out of shared/pdf_generator.py, which mixed these with
# domain-specific document layouts - a boundary violation for shared/,
# which must stay business-neutral).
# ===========================================================================
def fmt_date(d):
    return d.strftime("%d %b %Y") if d else "-"


def mask_value(value, keep_last=4):
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


def mask_phone(value):
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
