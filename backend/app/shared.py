"""Shared cross-domain utilities: email/phone/file-signature
validation, Excel export helpers (sheet writing, dropdowns,
instructions), and PDF document styling (header/footer/contact-block/
masking). Combines the former validators.py, exporters.py, and
document_style.py."""
import os
from io import BytesIO
from typing import Iterable, Sequence
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image as XLImage
from openpyxl.worksheet.datavalidation import DataValidation
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.platypus import Table, TableStyle, Paragraph, Image, Spacer
from reportlab.graphics.shapes import Drawing, Circle, Rect, Polygon


# --- validators.py ---
def validate_email(email: str) -> bool:
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_phone(phone: str) -> bool:
    """Mandatory rule: a mobile number must be exactly 10 digits - no
    country code prefix, no more, no less. Matches the Indian mobile
    number convention Woodful's own business data uses throughout.
    Callers should show 'Please enter valid mobile number' when this
    returns False (the exact wording used on both the client form and
    the Excel import error report).
    """
    import re
    pattern = r'^[0-9]{10}$'
    return re.match(pattern, phone) is not None


_FILE_SIGNATURES = {
    "pdf": [b"%PDF-"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "doc": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],  # legacy OLE compound file
    "docx": [b"PK\x03\x04", b"PK\x05\x06"],
    "xlsx": [b"PK\x03\x04", b"PK\x05\x06"],
}


def validate_file_signature(ext: str, header: bytes) -> bool:
    """Returns True if `header` (the first bytes read from the uploaded
    file) matches a known-good magic-byte signature for the claimed
    extension `ext`. Extensions with no signature registered (there are
    none currently expected to reach this function) fail closed."""
    signatures = _FILE_SIGNATURES.get(ext.lower())
    if not signatures:
        return False
    return any(header.startswith(sig) for sig in signatures)


# --- exporters.py ---
"""
Excel export helpers (openpyxl). These generate point-in-time snapshot
reports (like an invoice or statement), not editable models the user fills
in - so cells hold computed values directly rather than live formulas.
That also keeps report generation fast and dependency-free at request time
(no LibreOffice recalculation step needed for a web API response).
"""

FORMULA_INJECTION_PREFIXES = ("=", "+", "-", "@")


def _sanitize_cell_value(value):
    """Prevents Excel formula injection: user-controlled text (a client
    name, remark, task description, etc.) that happens to start with
    =, +, -, or @ would otherwise be interpreted as an executable
    formula the moment someone opens the downloaded file - not stored
    as literal text. Only applies to strings; numbers/dates/None pass
    through untouched, including real legitimate negative numbers,
    which are numeric types here, not strings starting with "-"."""
    if isinstance(value, str) and value.startswith(FORMULA_INJECTION_PREFIXES):
        return "'" + value
    return value


INK = "11110F"


GOLD = "C08A45"


IVORY = "F6F2EA"


BORDER_COLOR = "DED6C8"


HEADER_FONT = Font(name="Arial", bold=True, color="FFFFFF", size=11)


HEADER_FILL = PatternFill(start_color=INK, end_color=INK, fill_type="solid")


TITLE_FONT = Font(name="Arial", bold=True, size=15, color=INK)


SUBTITLE_FONT = Font(name="Arial", size=9, color="70685D")


BODY_FONT = Font(name="Arial", size=10)


ZEBRA_FILL = PatternFill(start_color=IVORY, end_color=IVORY, fill_type="solid")


GOLD_UNDERLINE = Border(bottom=Side(style="medium", color=GOLD))


CURRENCY_FORMAT = (
    '[>=10000000]"Rs "##\\,##\\,##\\,##0.00;'
    '[>=100000]"Rs "##\\,##\\,##0.00;'
    '"Rs "#,##0.00'
)


INTEGER_FORMAT = "#,##0;(#,##0);-"


PERCENT_FORMAT = "0.0%"


CURRENCY_COLUMNS = {
    "rate", "amount", "taxable_value", "gst_amount", "invoice_total", "average_rate",
    "stock_value", "order_value", "advance", "other_received", "total_received",
    "balance", "monthly_salary", "daily_wage", "gross_profit", "estimated_gross_profit",
    "total_stock_value", "purchase_value", "pending_payment", "project_expenses", "material_cost",
}


PERCENT_COLUMNS = {"gross_margin_ratio", "margin_percent", "completion_percent"}


LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "logo.png")


def _column_format(col_name: str) -> str:
    if col_name in CURRENCY_COLUMNS:
        return CURRENCY_FORMAT
    if col_name in PERCENT_COLUMNS:
        return PERCENT_FORMAT
    return "General"


def write_sheet(wb: Workbook, sheet_name: str, title: str, columns: Sequence[str],
                 rows: Iterable[dict], headers: Sequence[str] = None, total_columns: Sequence[str] = None,
                 subtitle: str = None, summary: Sequence[tuple] = None):
    """Writes one formatted sheet: logo + title row (+ optional subtitle row
    for "Generated on <date>" / filters-applied context), a styled header
    row, then one row per dict in `rows` (keyed by `columns`). If
    `total_columns` is given, appends a totals row using a real Excel
    =SUM() formula over those columns' cell range - not a Python-computed
    static value - so the workbook stays correct if someone edits a row
    after opening it, same as any real spreadsheet total should. If
    `summary` is given (a list of (label, value) pairs), appends a small
    summary block below the table - e.g. counts/totals broken down by
    payment mode - for reports where a single grand total isn't enough
    context on its own."""
    ws = wb.create_sheet(title=sheet_name[:31])  # Excel sheet name limit
    headers = headers or columns
    last_col = max(len(columns), 1)
    rows = list(rows)

    title_row = 1
    if os.path.exists(LOGO_PATH):
        img = XLImage(LOGO_PATH)
        img.width, img.height = 130, 33  # matches the logo's real aspect ratio
        ws.add_image(img, "A1")
        ws.row_dimensions[1].height = 28
        title_row = 2

    ws.cell(row=title_row, column=1, value=_sanitize_cell_value(title)).font = TITLE_FONT
    ws.merge_cells(start_row=title_row, start_column=1, end_row=title_row, end_column=last_col)
    ws.cell(row=title_row, column=1).border = GOLD_UNDERLINE
    for c in range(2, last_col + 1):
        ws.cell(row=title_row, column=c).border = GOLD_UNDERLINE

    subtitle_row = title_row
    if subtitle:
        subtitle_row = title_row + 1
        ws.cell(row=subtitle_row, column=1, value=_sanitize_cell_value(subtitle)).font = SUBTITLE_FONT
        ws.merge_cells(start_row=subtitle_row, start_column=1, end_row=subtitle_row, end_column=last_col)

    header_row = subtitle_row + 2
    for idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=idx, value=_sanitize_cell_value(header))
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")

    first_data_row = header_row + 1
    row_num = first_data_row
    for i, row in enumerate(rows):
        for idx, col in enumerate(columns, start=1):
            cell = ws.cell(row=row_num, column=idx, value=_sanitize_cell_value(row.get(col)))
            cell.font = BODY_FONT
            cell.number_format = _column_format(col)
            if i % 2 == 1:
                cell.fill = ZEBRA_FILL
        row_num += 1
    last_data_row = row_num - 1

    if total_columns and rows:
        total_row = row_num
        ws.cell(row=total_row, column=1, value="Total").font = Font(name="Arial", bold=True, size=10, color="FFFFFF")
        for idx, col in enumerate(columns, start=1):
            cell = ws.cell(row=total_row, column=idx)
            cell.fill = PatternFill(start_color=GOLD, end_color=GOLD, fill_type="solid")
            if col in total_columns:
                col_letter = get_column_letter(idx)
                cell.value = f"=SUM({col_letter}{first_data_row}:{col_letter}{last_data_row})"
                cell.font = Font(name="Arial", bold=True, size=10, color="FFFFFF")
                cell.number_format = _column_format(col)
        row_num += 1

    if summary:
        row_num += 1  # blank separator row
        summary_header_row = row_num
        ws.cell(row=summary_header_row, column=1, value="Summary").font = Font(name="Arial", bold=True, size=11, color=INK)
        row_num += 1
        for label, value in summary:
            # Caller passes `value` pre-formatted (e.g. "Rs 1,25,000.00" or
            # "42 payments") rather than a raw number, since a summary block
            # mixes genuinely different kinds of figures (currency, counts,
            # percentages) that a single inferred number_format can't
            # correctly guess between.
            ws.cell(row=row_num, column=1, value=_sanitize_cell_value(label)).font = Font(name="Arial", bold=True, size=10)
            ws.cell(row=row_num, column=2, value=_sanitize_cell_value(value)).font = BODY_FONT
            row_num += 1

    for idx, col in enumerate(columns, start=1):
        header_len = len(str(headers[idx - 1]))
        ws.column_dimensions[get_column_letter(idx)].width = max(header_len + 2, 14)

    ws.freeze_panes = f"A{header_row + 1}"
    ws.woodful_header_row = header_row  # first data row = header_row + 1; used by callers adding dropdown validation

    # Filters (dropdown arrows on the header row) and print setup - applies
    # to every export sheet, not just this one, since every report benefits
    # from being filterable and printable without per-caller boilerplate.
    if rows:
        ws.auto_filter.ref = f"A{header_row}:{get_column_letter(last_col)}{last_data_row}"
    ws.print_options.horizontalCentered = False
    ws.page_setup.orientation = "landscape" if last_col > 6 else "portrait"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = f"{header_row}:{header_row}"

    return ws


def add_dropdown_validation(ws, column_letter: str, values: Sequence[str], first_row: int, last_row: int = 1000):
    """Excel dropdown for a genuine controlled-value column -
    only call this where the same value list also exists in
    the UI/backend (e.g. Client Type). `last_row` defaults generously so
    the dropdown still applies to rows a user adds below the sample data."""
    dv = DataValidation(type="list", formula1=f'"{",".join(values)}"', allow_blank=True, showDropDown=False)
    dv.error = f"Please choose one of: {', '.join(values)}"
    dv.errorTitle = "Invalid value"
    ws.add_data_validation(dv)
    dv.add(f"{column_letter}{first_row}:{column_letter}{last_row}")
    return dv


def write_instructions_sheet(wb: Workbook, template_name: str, version: str, field_docs: list,
                              id_rule: str = None, duplicate_rule: str = None,
                              blank_row_rule: str = None, relationship_notes: list = None,
                              extra_notes: list = None):
    """Every import workbook must have an
    Instructions tab. One shared implementation so every Woodful import
    workbook explains its fields, ID rule, and blank-row handling the
    same way rather than each importer hand-rolling its own text sheet.

    field_docs: list of dicts with keys name, mandatory (bool), meaning,
    format, accepted_values (optional). Mandatory fields are marked the
    same "*" convention used on the Data sheet header (section 4).
    """
    ws = wb.create_sheet(title="Instructions")
    row = 1
    if os.path.exists(LOGO_PATH):
        img = XLImage(LOGO_PATH)
        img.width, img.height = 130, 33
        ws.add_image(img, "A1")
        ws.row_dimensions[1].height = 28
        row = 2

    ws.cell(row=row, column=1, value=_sanitize_cell_value(f"{template_name}")).font = TITLE_FONT
    row += 1
    ws.cell(row=row, column=1, value=_sanitize_cell_value(f"Version: {version}")).font = SUBTITLE_FONT
    row += 2

    ws.cell(row=row, column=1, value="* = Mandatory field").font = Font(name="Arial", bold=True, size=10, color=INK)
    row += 2

    headers = ["Field", "Mandatory", "Meaning", "Format / Accepted Values"]
    for idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=idx, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
    row += 1
    for i, field in enumerate(field_docs):
        ws.cell(row=row, column=1, value=_sanitize_cell_value(field["name"])).font = BODY_FONT
        ws.cell(row=row, column=2, value="Yes" if field.get("mandatory") else "No").font = BODY_FONT
        ws.cell(row=row, column=3, value=_sanitize_cell_value(field.get("meaning", ""))).font = BODY_FONT
        accepted = field.get("accepted_values")
        fmt = field.get("format", "")
        combined = f"{fmt}" + (f" Accepted values: {', '.join(accepted)}." if accepted else "")
        cell = ws.cell(row=row, column=4, value=_sanitize_cell_value(combined))
        cell.font = BODY_FONT
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        if i % 2 == 1:
            for c in range(1, 5):
                ws.cell(row=row, column=c).fill = ZEBRA_FILL
        row += 1

    row += 1
    ws.cell(row=row, column=1, value="ID Rule").font = Font(name="Arial", bold=True, size=10, color=INK)
    row += 1
    ws.cell(row=row, column=1, value=_sanitize_cell_value(id_rule or "IDs are system-generated. Do not add or edit an ID column.")).font = BODY_FONT
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
    row += 2

    ws.cell(row=row, column=1, value="Duplicate / Typo Handling").font = Font(name="Arial", bold=True, size=10, color=INK)
    row += 1
    ws.cell(row=row, column=1, value=_sanitize_cell_value(duplicate_rule or (
        "A row that closely matches an existing record is flagged as a possible match during preview - "
        "you will be asked to confirm whether to use the existing record or create a new one. "
        "Matches are never created or merged automatically."
    ))).font = BODY_FONT
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
    row += 2

    ws.cell(row=row, column=1, value="Blank Rows").font = Font(name="Arial", bold=True, size=10, color=INK)
    row += 1
    ws.cell(row=row, column=1, value=_sanitize_cell_value(blank_row_rule or (
        "A completely empty row is ignored. A partially filled row (e.g. only some columns filled in) "
        "is validated and will show an error if a mandatory field is missing."
    ))).font = BODY_FONT
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
    row += 2

    if relationship_notes:
        ws.cell(row=row, column=1, value="Sheet Relationships").font = Font(name="Arial", bold=True, size=10, color=INK)
        row += 1
        for note in relationship_notes:
            ws.cell(row=row, column=1, value=_sanitize_cell_value(note)).font = BODY_FONT
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
            row += 1
        row += 1

    if extra_notes:
        ws.cell(row=row, column=1, value="Other Notes").font = Font(name="Arial", bold=True, size=10, color=INK)
        row += 1
        for note in extra_notes:
            ws.cell(row=row, column=1, value=_sanitize_cell_value(note)).font = BODY_FONT
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
            row += 1

    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 12
    ws.column_dimensions["C"].width = 38
    ws.column_dimensions["D"].width = 48
    return ws


def build_workbook(sheets: list) -> BytesIO:
    """sheets: list of dicts, each with keys: sheet_name, title, columns,
    rows, and optional headers, total_columns, subtitle. Returns an
    in-memory xlsx file."""
    wb = Workbook()
    wb.remove(wb.active)  # drop the default blank sheet
    for spec in sheets:
        write_sheet(wb, spec["sheet_name"], spec["title"], spec["columns"], spec["rows"],
                    spec.get("headers"), spec.get("total_columns"), spec.get("subtitle"), spec.get("summary"))

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def xlsx_response(buffer, filename: str) -> StreamingResponse:
    """Wraps an in-memory xlsx buffer (from build_workbook) as a
    downloadable FastAPI response - shared by every domain's
    modules/*/api/reports.py route module so
    the Content-Disposition/Cache-Control headers stay identical across
    all of them rather than each domain module repeating its own copy."""
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store, private",
        },
    )


# --- document_style.py ---
"""Shared Woodful Creations document design system - used by every PDF
this application generates, so an estimate, an invoice, and a salary
slip all look like they came from the same professional business, not
three unrelated generic reports.

Palette matches the actual application design system (near-black ink,
warm ivory, refined gold) - not the generic reportlab default blue.

PDF_-prefixed: these are reportlab Color objects, deliberately
distinct names from the plain hex-string INK/GOLD/IVORY/BORDER_COLOR
defined above in the exporters.py section for openpyxl. Reusing the
same names here previously reassigned those globals at module-import
time, so by the time any Excel-writing function below actually ran,
INK/GOLD/IVORY had silently become reportlab Color objects instead of
the hex strings openpyxl's Font/PatternFill require - "Font.color
should be openpyxl Color" / "PatternFill.fgColor should be openpyxl
Color". Do not reuse the unprefixed names for anything reportlab/PDF
here - openpyxl and reportlab represent color completely differently
and one file needs to hand out the right kind to each caller.
"""

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


PDF_INK = colors.HexColor("#3B1400")


PDF_CHARCOAL = colors.HexColor("#1A1916")


PDF_IVORY = colors.HexColor("#F6F2EA")


PDF_GOLD = colors.HexColor("#C08A45")


PDF_BORDER = colors.HexColor("#DED6C8")


PDF_TEXT_SECONDARY = colors.HexColor("#70685D")


LOGO_ASPECT = 609 / 2435  # native pixel dimensions of assets/logo.png


def _icon_pin(size=9):
    """Location pin - a circle sitting on a downward point, the same
    silhouette used in the approved letterhead's contact block. Drawn
    as vector shapes (reportlab's base fonts have no pin/phone/
    envelope/camera glyphs to fall back on), colored to match PDF_INK."""
    d = Drawing(size, size)
    cx = size / 2
    d.add(Polygon(points=[cx - size * 0.28, size * 0.42, cx + size * 0.28, size * 0.42, cx, 0], fillColor=PDF_INK, strokeColor=None))
    d.add(Circle(cx, size * 0.62, size * 0.38, fillColor=PDF_INK, strokeColor=None))
    d.add(Circle(cx, size * 0.62, size * 0.15, fillColor=colors.white, strokeColor=None))
    return d


def _icon_phone(size=9):
    """Simple rounded handset body - the pragmatic simplification a
    small monochrome print icon needs at 9pt, rather than attempting a
    literally accurate handset silhouette with reportlab's basic
    shape primitives."""
    d = Drawing(size, size)
    d.add(Rect(size * 0.22, size * 0.02, size * 0.56, size * 0.96, size * 0.22, size * 0.22, fillColor=PDF_INK, strokeColor=None))
    return d


def _icon_envelope(size=9):
    """Envelope: an outlined rectangle with a V-fold drawn on top in
    the page's background color, matching a standard mail glyph."""
    d = Drawing(size, size * 0.72)
    h = size * 0.72
    d.add(Rect(0, 0, size, h, fillColor=PDF_INK, strokeColor=None))
    d.add(Polygon(points=[size * 0.08, h * 0.85, size / 2, h * 0.35, size * 0.92, h * 0.85], fillColor=colors.white, strokeColor=None))
    return d


def _icon_instagram(size=9):
    """Rounded-square camera outline with a center ring and a small
    corner dot - the recognizable Instagram glyph shape, drawn flat/
    monochrome to match the other print icons rather than reproducing
    the brand's actual multicolor logo."""
    d = Drawing(size, size)
    d.add(Rect(0, 0, size, size, size * 0.28, size * 0.28, fillColor=None, strokeColor=PDF_INK, strokeWidth=size * 0.11))
    d.add(Circle(size / 2, size / 2, size * 0.26, fillColor=None, strokeColor=PDF_INK, strokeWidth=size * 0.11))
    d.add(Circle(size * 0.78, size * 0.78, size * 0.07, fillColor=PDF_INK, strokeColor=None))
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
    line_style = ParagraphStyle("HeaderContactLine", parent=styles["body"], fontSize=8.5, leading=11, textColor=PDF_TEXT_SECONDARY)
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
            textColor=PDF_INK, spaceAfter=2,
        ),
        "doc_subtitle": ParagraphStyle(
            "DocSubtitle", parent=base["Normal"], fontName="Helvetica", fontSize=9,
            textColor=PDF_TEXT_SECONDARY, spaceAfter=0,
        ),
        "section_label": ParagraphStyle(
            "SectionLabel", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8,
            textColor=PDF_GOLD, spaceAfter=4, spaceBefore=10,
        ),
        "body": ParagraphStyle(
            "Body", parent=base["Normal"], fontName="Helvetica", fontSize=9.5,
            textColor=PDF_INK, leading=14,
        ),
        "body_secondary": ParagraphStyle(
            "BodySecondary", parent=base["Normal"], fontName="Helvetica", fontSize=8.5,
            textColor=PDF_TEXT_SECONDARY, leading=13,
        ),
        "table_cell": ParagraphStyle(
            "TableCell", parent=base["Normal"], fontName="Helvetica", fontSize=9,
            textColor=PDF_INK, leading=11.5,
        ),
        "total_label": ParagraphStyle(
            "TotalLabel", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=11,
            textColor=colors.white, alignment=TA_RIGHT,
        ),
        "footer": ParagraphStyle(
            "Footer", parent=base["Normal"], fontName="Helvetica", fontSize=7.5,
            textColor=PDF_TEXT_SECONDARY, alignment=TA_CENTER,
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
    solid PDF_GOLD bar; the reference has no such bar, just a hairline
    rule, so this now draws a 0.75pt PDF_INK-colored line instead."""
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
                           style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), PDF_INK)])))
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
    "PAYMENT & LEAVE INFORMATION" convention exactly (same PDF_INK
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
        ("BACKGROUND", (0, 0), (-1, -1), PDF_IVORY),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]
    if title:
        title_cell = Paragraph(f'<font color="#FFFFFF" size="8.5"><b>{pdf_text(title)}</b></font>', styles["body"])
        span_width = sum(col_widths)
        data = [[title_cell] + [""] * (len(col_widths) - 1)] + data
        style_commands += [
            ("SPAN", (0, 0), (-1, 0)),
            ("BACKGROUND", (0, 0), (-1, 0), PDF_INK),
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
        ("BACKGROUND", (0, 0), (-1, 0), PDF_INK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("GRID", (0, 0), (-1, len(data_rows)), 0.5, PDF_BORDER),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
    ]
    for i in range(1, len(data_rows) + 1):
        if i % 2 == 0:
            style_commands.append(("BACKGROUND", (0, i), (-1, i), PDF_IVORY))

    if totals_rows:
        start = len(table_data)
        table_data += totals_rows
        for i, row in enumerate(totals_rows):
            row_idx = start + i
            is_grand_total = i == len(totals_rows) - 1
            if is_grand_total:
                style_commands += [
                    ("BACKGROUND", (0, row_idx), (-1, row_idx), PDF_GOLD),
                    ("TEXTCOLOR", (0, row_idx), (-1, row_idx), colors.white),
                    ("FONTNAME", (0, row_idx), (-1, row_idx), "Helvetica-Bold"),
                    ("FONTSIZE", (0, row_idx), (-1, row_idx), 11),
                ]
            else:
                style_commands += [
                    ("FONTNAME", (0, row_idx), (-1, row_idx), "Helvetica-Bold"),
                    ("LINEABOVE", (0, row_idx), (-1, row_idx), 0.5, PDF_BORDER),
                ]

    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle(style_commands))
    return t


def build_footer_text(extra_line: str = None) -> str:
    lines = ["Woodful Creations &middot; This is a system-generated document."]
    if extra_line:
        lines.append(extra_line)
    return "<br/>".join(lines)


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
