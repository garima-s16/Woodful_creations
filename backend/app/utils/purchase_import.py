"""Excel import for purchases - one fixed template, so the download
(what the user fills in) and the parser (what reads it back) can never
drift out of sync, since both reference this same column list.

Never writes a parsed row directly to the database - every upload goes
through preview() first (matches against real Material/Supplier
records, validates each row, never commits), and only commit() actually
creates records, and only for rows the caller explicitly confirms.
"""
from io import BytesIO
from decimal import Decimal, InvalidOperation
from datetime import datetime
from typing import List, Optional

import openpyxl
from openpyxl import Workbook

from app.utils.exporters import write_sheet

# The one fixed set of columns - the template download and the parser
# both use this list, never a separately-typed-out copy of the header
# names, so they can't silently disagree about what a column is called.
PURCHASE_IMPORT_COLUMNS = [
    "Material", "Specification", "Quantity", "Unit", "Supplier",
    "Rate", "GST %", "Invoice Number", "Invoice Date", "Remarks",
]

EXAMPLE_ROWS = [
    {
        "Material": "HDHMR 18mm", "Specification": "Greenpanel, 8x4 ft", "Quantity": 5, "Unit": "Sheets",
        "Supplier": "Sanket Plywood & Boards", "Rate": 1820, "GST %": 18,
        "Invoice Number": "INV-1001", "Invoice Date": "2026-08-01", "Remarks": "",
    },
    {
        "Material": "BWP Plywood 18mm", "Specification": "Century, 8x4 ft", "Quantity": 6, "Unit": "Sheets",
        "Supplier": "Century Plywood Dealer", "Rate": 2350, "GST %": 18,
        "Invoice Number": "INV-1001", "Invoice Date": "2026-08-01", "Remarks": "Delivered with Aug 1 batch",
    },
]


def build_import_template() -> BytesIO:
    """The downloadable .xlsx a user fills in - real Woodful branding
    (via write_sheet, the same helper every other export uses), two
    example rows showing the expected format, and nothing else - no
    totals row, since this is an input template, not a report."""
    wb = Workbook()
    wb.remove(wb.active)
    write_sheet(
        wb, sheet_name="Purchase Import", title="Woodful Creations - Purchase Import Template",
        subtitle="Fill in one row per material purchased. Do not change the column headers.",
        columns=PURCHASE_IMPORT_COLUMNS, rows=EXAMPLE_ROWS,
    )
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def _clean(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value if value else None
    return value


def parse_uploaded_workbook(file_bytes: bytes) -> List[dict]:
    """Reads the uploaded file against the fixed column list, returning
    one raw dict per row (empty rows skipped). Does no matching or
    validation here - that's preview()'s job, kept separate so parsing
    failures (a genuinely malformed file) are distinguishable from
    validation failures (a well-formed file with bad data)."""
    wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True)
    ws = wb.worksheets[0]

    header_row_idx = None
    header_cells = None
    for row in ws.iter_rows(min_row=1, max_row=10):
        values = [str(c.value).strip() if c.value is not None else "" for c in row]
        if all(col in values for col in PURCHASE_IMPORT_COLUMNS):
            header_row_idx = row[0].row
            header_cells = values
            break
    if header_row_idx is None:
        raise ValueError(
            "Couldn't find the expected column headers in this file. "
            "Please use the downloaded template without changing the header row."
        )

    col_index = {name: header_cells.index(name) for name in PURCHASE_IMPORT_COLUMNS}
    rows = []
    for row in ws.iter_rows(min_row=header_row_idx + 1):
        values = [c.value for c in row]
        if all(_clean(v) is None for v in values):
            continue  # skip fully blank rows
        rows.append({name: _clean(values[idx]) if idx < len(values) else None for name, idx in col_index.items()})
    return rows


def validate_and_match_row(row: dict, db, materials_by_name, suppliers_by_name):
    """Validates one parsed row and matches it against real Material/
    Supplier records (case-insensitive exact match on name - not fuzzy,
    per the standing project principle against silently merging records
    on a guess). Returns (result_dict, errors_list). Never writes
    anything - this is pure validation/matching."""
    errors = []
    material_name = row.get("Material")
    supplier_name = row.get("Supplier")

    if not material_name:
        errors.append("Material name is required")
    if not supplier_name:
        errors.append("Supplier is required")

    quantity = None
    if row.get("Quantity") is None:
        errors.append("Quantity is required")
    else:
        try:
            quantity = Decimal(str(row["Quantity"]))
            if quantity <= 0:
                errors.append("Quantity must be greater than zero")
        except (InvalidOperation, ValueError):
            errors.append(f"Invalid quantity: {row['Quantity']!r}")

    rate = None
    if row.get("Rate") is None:
        errors.append("Rate is required")
    else:
        try:
            rate = Decimal(str(row["Rate"]))
            if rate < 0:
                errors.append("Rate cannot be negative")
        except (InvalidOperation, ValueError):
            errors.append(f"Invalid rate: {row['Rate']!r}")

    gst_percent = Decimal("0")
    if row.get("GST %") is not None:
        try:
            gst_percent = Decimal(str(row["GST %"]))
        except (InvalidOperation, ValueError):
            errors.append(f"Invalid GST %: {row['GST %']!r}")

    invoice_date = None
    if row.get("Invoice Date"):
        raw = row["Invoice Date"]
        if isinstance(raw, datetime):
            invoice_date = raw
        else:
            try:
                invoice_date = datetime.strptime(str(raw), "%Y-%m-%d")
            except ValueError:
                errors.append(f"Invoice Date must be YYYY-MM-DD, got {raw!r}")

    matched_material = materials_by_name.get((material_name or "").strip().lower()) if material_name else None
    matched_supplier = suppliers_by_name.get((supplier_name or "").strip().lower()) if supplier_name else None
    if material_name and not matched_material:
        errors.append(f'No existing material matches "{material_name}" - it can be created on import, or create it first and re-upload.')
    if supplier_name and not matched_supplier:
        errors.append(f'No existing supplier matches "{supplier_name}" - create it on the Suppliers page first, then re-upload.')

    result = {
        "material_name": material_name, "specification": row.get("Specification"),
        "quantity": quantity, "unit": row.get("Unit") or "Nos", "supplier_name": supplier_name,
        "rate": rate, "gst_percent": gst_percent, "invoice_number": row.get("Invoice Number"),
        "invoice_date": invoice_date, "remarks": row.get("Remarks"),
        "matched_material_id": matched_material.id if matched_material else None,
        "matched_supplier_id": matched_supplier.id if matched_supplier else None,
        "is_new_material": bool(material_name) and not matched_material,
    }
    return result, errors
