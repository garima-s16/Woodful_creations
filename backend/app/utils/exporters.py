"""
Excel export helpers (openpyxl). These generate point-in-time snapshot
reports (like an invoice or statement), not editable models the user fills
in - so cells hold computed values directly rather than live formulas.
That also keeps report generation fast and dependency-free at request time
(no LibreOffice recalculation step needed for a web API response).
"""
import os
from io import BytesIO
from typing import Iterable, Sequence

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image as XLImage

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

# Excel's number format mini-language doesn't have a portable built-in for
# Indian digit grouping (1,25,000 not 125,000) that renders correctly
# regardless of the viewer's locale settings - locale-code formats like
# [$-4009] depend on the reader's OS/Excel locale and can silently fall
# back to Western grouping. This conditional format instead encodes the
# lakh/crore comma positions directly, so it looks the same everywhere.
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
PERCENT_COLUMNS = {"gross_margin_percent", "margin_percent", "completion_percent"}

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

    ws.cell(row=title_row, column=1, value=title).font = TITLE_FONT
    ws.merge_cells(start_row=title_row, start_column=1, end_row=title_row, end_column=last_col)
    ws.cell(row=title_row, column=1).border = GOLD_UNDERLINE
    for c in range(2, last_col + 1):
        ws.cell(row=title_row, column=c).border = GOLD_UNDERLINE

    subtitle_row = title_row
    if subtitle:
        subtitle_row = title_row + 1
        ws.cell(row=subtitle_row, column=1, value=subtitle).font = SUBTITLE_FONT
        ws.merge_cells(start_row=subtitle_row, start_column=1, end_row=subtitle_row, end_column=last_col)

    header_row = subtitle_row + 2
    for idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=idx, value=header)
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
