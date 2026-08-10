"""
Excel export helpers (openpyxl). These generate point-in-time snapshot
reports (like an invoice or statement), not editable models the user fills
in - so cells hold computed values directly rather than live formulas.
That also keeps report generation fast and dependency-free at request time
(no LibreOffice recalculation step needed for a web API response).
"""
from io import BytesIO
from typing import Any, Iterable, Sequence

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

HEADER_FONT = Font(name="Arial", bold=True, color="FFFFFF", size=11)
HEADER_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
BODY_FONT = Font(name="Arial", size=10)
TITLE_FONT = Font(name="Arial", bold=True, size=14)
CURRENCY_FORMAT = "#,##0.00;(#,##0.00);-"
INTEGER_FORMAT = "#,##0;(#,##0);-"
PERCENT_FORMAT = "0.0%"

CURRENCY_COLUMNS = {
    "rate", "amount", "taxable_value", "gst_amount", "invoice_total", "average_rate",
    "stock_value", "order_value", "advance", "other_received", "total_received",
    "balance", "monthly_salary", "daily_wage", "gross_profit", "estimated_gross_profit",
    "total_stock_value", "purchase_value", "pending_payment", "project_expenses",
}
PERCENT_COLUMNS = {"gross_margin_percent", "margin_percent", "completion_percent"}


def _column_format(col_name: str) -> str:
    if col_name in CURRENCY_COLUMNS:
        return CURRENCY_FORMAT
    if col_name in PERCENT_COLUMNS:
        return PERCENT_FORMAT
    return "General"


def write_sheet(wb: Workbook, sheet_name: str, title: str, columns: Sequence[str],
                 rows: Iterable[dict], headers: Sequence[str] = None):
    """Writes one formatted sheet: a title row, a styled header row, then
    one row per dict in `rows` (keyed by `columns`)."""
    ws = wb.create_sheet(title=sheet_name[:31])  # Excel sheet name limit
    headers = headers or columns

    ws.cell(row=1, column=1, value=title).font = TITLE_FONT
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(len(columns), 1))

    header_row = 3
    for idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=idx, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")

    row_num = header_row + 1
    for row in rows:
        for idx, col in enumerate(columns, start=1):
            cell = ws.cell(row=row_num, column=idx, value=row.get(col))
            cell.font = BODY_FONT
            cell.number_format = _column_format(col)
        row_num += 1

    for idx, col in enumerate(columns, start=1):
        header_len = len(str(headers[idx - 1]))
        ws.column_dimensions[get_column_letter(idx)].width = max(header_len + 2, 14)

    ws.freeze_panes = f"A{header_row + 1}"
    return ws


def build_workbook(sheets: list) -> BytesIO:
    """sheets: list of dicts, each with keys: sheet_name, title, columns,
    rows, and optional headers. Returns an in-memory xlsx file."""
    wb = Workbook()
    wb.remove(wb.active)  # drop the default blank sheet
    for spec in sheets:
        write_sheet(wb, spec["sheet_name"], spec["title"], spec["columns"], spec["rows"],
                    spec.get("headers"))

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
