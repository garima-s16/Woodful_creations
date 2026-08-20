"""Excel import for purchases - one fixed template, so the download
(what the user fills in) and the parser (what reads it back) can never
drift out of sync, since both reference this same column list.

Never writes a parsed row directly to the database - every upload goes
through preview() first (matches against real Material/Supplier
records, validates each row, never commits), and only commit() actually
creates records, and only for rows the caller explicitly confirms.
"""
import re
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

# Controlled header alias table (Family 6) - real business Excel files
# rarely match the template's header row byte-for-byte ("Material Name"
# instead of "Material", "GST%" instead of "GST %", different
# capitalization...). Every key here is matched case/whitespace-
# insensitively against an uploaded header cell; this is deliberately a
# short, explicit list rather than any kind of fuzzy match - an
# unrelated column can never be silently treated as a required one.
HEADER_ALIASES = {
    "material": "Material",
    "material name": "Material",
    "specification": "Specification",
    "spec": "Specification",
    "specifications": "Specification",
    "quantity": "Quantity",
    "qty": "Quantity",
    "unit": "Unit",
    "units": "Unit",
    "supplier": "Supplier",
    "supplier name": "Supplier",
    "rate": "Rate",
    "invoice number": "Invoice Number",
    "invoice no": "Invoice Number",
    "invoice no.": "Invoice Number",
    "invoice #": "Invoice Number",
    "invoice date": "Invoice Date",
    "date": "Invoice Date",
    "invoice dt": "Invoice Date",
    "remarks": "Remarks",
    "remark": "Remarks",
    "gst": "GST %",
    "gst%": "GST %",
    "gst %": "GST %",
}
# Every canonical column name also maps to itself (case-insensitive) -
# the alias table above only needs to list the *variations*, not repeat
# every already-correct header too.
for _col in PURCHASE_IMPORT_COLUMNS:
    HEADER_ALIASES.setdefault(_col.lower(), _col)


def _normalize_header_cell(raw) -> Optional[str]:
    """One raw header cell -> its canonical column name (e.g. "  Material Name"
    -> "Material"), or None if it isn't recognized. Whitespace/case
    differences only - never a partial or fuzzy match, so a genuinely
    unrelated column is never mistaken for a required one."""
    if raw is None:
        return None
    key = re.sub(r"\s+", " ", str(raw).strip().lower())
    return HEADER_ALIASES.get(key)


def _resolve_header_row(values) -> Optional[dict]:
    """Given one worksheet row's raw cell values, tries to resolve every
    required column to exactly one cell index. Returns
    {canonical_name: column_index} only if every required column was
    matched exactly once; returns None if this isn't a valid header row -
    either something required is missing, or two cells both claim the
    same canonical column (e.g. both "Material" and "Material Name"
    present), which is treated as ambiguous rather than guessed at."""
    resolved = {}
    for idx, raw in enumerate(values):
        canonical = _normalize_header_cell(raw)
        if canonical is None:
            continue
        if canonical in resolved:
            return None
        resolved[canonical] = idx
    if all(col in resolved for col in PURCHASE_IMPORT_COLUMNS):
        return resolved
    return None


# Strips thousands separators, common currency symbols, and a trailing
# "%" before a value is parsed as a number - "1,250" / "₹1,250" / "18%"
# all become plain numeric text. Never touches digits/decimal
# point/minus sign, so a genuinely invalid value still fails to parse
# afterwards rather than being coerced into something silently wrong.
_NUMERIC_NOISE_RE = re.compile(r"[₹$€£%,\s]")


def normalize_number(raw) -> Optional[Decimal]:
    """Real-world quantity/rate/GST% formatting -> Decimal, or None if
    nothing usable is left. None is a "couldn't parse" signal for the
    caller to report as a validation error - never a silently-defaulted
    0."""
    if raw is None:
        return None
    if isinstance(raw, (int, float, Decimal)):
        return Decimal(str(raw))
    text = _NUMERIC_NOISE_RE.sub("", str(raw))
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


# A small, explicit set of real-world date formats. Day-first formats
# are tried before month-first ones deliberately - this is an Indian
# business's purchase/GST workflow, where "01/08/2026" means 1 August,
# not January 8th - so an ambiguous D/M vs M/D string is resolved the
# same way a person filling in this template would read it, not by
# guessing per-cell.
_DATE_FORMATS = [
    "%Y-%m-%d", "%Y/%m/%d",
    "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",
    "%d-%b-%Y", "%d %b %Y", "%d %B %Y",
    "%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%B %d %Y",
]


def normalize_date(raw) -> Optional[datetime]:
    """Real-world date formatting -> datetime, or None if nothing in
    _DATE_FORMATS matches. An unparseable or impossible date (e.g.
    31 Feb) is never silently accepted - None means the caller reports
    it as a validation error."""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def normalize_match_key(name: Optional[str]) -> str:
    """The same case/whitespace-insensitive key used on both sides of
    Material/Supplier matching (building the by-name lookup AND looking
    a row's typed name up in it) - so "  hdhmr  18mm" and "HDHMR   18mm"
    match each other without this ever becoming fuzzy matching that could
    pick the wrong record. Collapses internal whitespace as well as
    trimming, which the existing .strip().lower() alone did not."""
    return re.sub(r"\s+", " ", (name or "").strip().lower())


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
    """Reads the uploaded file against the fixed column list (tolerating
    reasonable header variations - see HEADER_ALIASES/_resolve_header_row),
    returning one raw dict per row (empty rows skipped). Does no value
    normalization or matching/validation here - that's preview()'s job,
    kept separate so parsing failures (a genuinely malformed file, or one
    where a required column can't be confidently identified) are
    distinguishable from validation failures (a well-formed file with bad
    data)."""
    wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True)
    ws = wb.worksheets[0]

    header_row_idx = None
    col_index = None
    for row in ws.iter_rows(min_row=1, max_row=10):
        values = [c.value for c in row]
        resolved = _resolve_header_row(values)
        if resolved:
            header_row_idx = row[0].row
            col_index = resolved
            break
    if header_row_idx is None:
        raise ValueError(
            "Couldn't find the expected column headers in this file. "
            "Please use the downloaded template, or make sure every required "
            "column (Material, Quantity, Unit, Supplier, Rate, GST %, "
            "Invoice Number, Invoice Date, Specification, Remarks) has a "
            "recognizable header and isn't duplicated."
        )

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
        # normalize_number handles "1,250" / " 1250 " / currency symbols
        # (see HEADER/VALUE NORMALIZATION note above) before the
        # existing >0 check - an invalid quantity is still rejected the
        # same as before, just after stripping harmless formatting.
        quantity = normalize_number(row["Quantity"])
        if quantity is None:
            errors.append(f"Invalid quantity: {row['Quantity']!r}")
        elif quantity <= 0:
            errors.append("Quantity must be greater than zero")

    rate = None
    if row.get("Rate") is None:
        errors.append("Rate is required")
    else:
        rate = normalize_number(row["Rate"])
        if rate is None:
            errors.append(f"Invalid rate: {row['Rate']!r}")
        elif rate < 0:
            errors.append("Rate cannot be negative")

    gst_percent = Decimal("0")
    if row.get("GST %") is not None:
        normalized_gst = normalize_number(row["GST %"])
        if normalized_gst is None:
            errors.append(f"Invalid GST %: {row['GST %']!r}")
        else:
            gst_percent = normalized_gst

    invoice_date = None
    if row.get("Invoice Date"):
        raw = row["Invoice Date"]
        invoice_date = normalize_date(raw)
        if invoice_date is None:
            errors.append(f"Invoice Date must be a recognizable date (e.g. 2026-08-01 or 01-08-2026), got {raw!r}")

    matched_material = materials_by_name.get(normalize_match_key(material_name)) if material_name else None
    matched_supplier = suppliers_by_name.get(normalize_match_key(supplier_name)) if supplier_name else None
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
