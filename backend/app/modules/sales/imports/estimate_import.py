"""Excel import for Estimates - the
first Estimate import implementation; none existed before this.

Same discipline as app/utils/purchase_import.py / product_import.py /
client_import.py: one fixed template shared by the download and the
parser, never writes a parsed row directly to the database - preview()
validates/matches everything and commit() only applies rows the caller
has explicitly reviewed and confirmed.

Two differences from the other single-sheet imports, both required by
the spec:

1. Two related sheets, not one - "Estimate Header" (one row per
   estimate) and "Estimate Items" (one or more rows per estimate,
   linked back to the header by "Estimate Row #" - a spreadsheet-local
   reference, not a database ID, since a brand-new estimate has no
   Estimate ID yet at upload time).

2. Estimate ID rules (spec section 16) - blank creates a new Estimate
   (server-generated code), a valid existing estimate_code recognizes
   that Estimate for the edit/re-import workflow, and an unrecognized
   non-blank value is REJECTED rather than silently creating a new
   Estimate under a made-up ID. The same rule applies to Product ID on
   items (spec section 15): blank or unknown is rejected outright -
   this importer never creates a Product as a side effect of an
   Estimate import.

Totals are never trusted from the workbook (spec section 23) - rate/
quantity/discount/tax are read from Excel, but Subtotal/Tax/Grand Total
are always recomputed server-side via app.modules.sales.calculations.compute_totals,
the same function the Estimate UI's own create/update path uses.
"""
from io import BytesIO
from decimal import Decimal, InvalidOperation
from typing import List

from app.shared.import_common import _clean, resolve_header_row_with_aliases, normalize_phone_key
import openpyxl
from openpyxl import Workbook

from app.shared.exporters import write_sheet

# ---------------------------------------------------------------------------
# Column definitions
# ---------------------------------------------------------------------------

HEADER_COLUMNS = [
    "Estimate ID", "Client Name", "Client Phone", "Estimate Date",
    "Valid Until", "Margin %", "Discount", "Tax %", "Notes",
]

ITEMS_COLUMNS = [
    "Estimate Row #", "Estimate ID", "Product ID", "Description",
    "Category", "Quantity", "Unit", "Rate", "Discount %", "Tax %",
]

HEADER_ALIASES = {
    "estimate id": "Estimate ID", "estimate code": "Estimate ID", "id": "Estimate ID",
    "client name": "Client Name", "client": "Client Name",
    "client phone": "Client Phone", "phone": "Client Phone",
    "estimate date": "Estimate Date", "date": "Estimate Date",
    "valid until": "Valid Until", "valid till": "Valid Until", "expiry": "Valid Until",
    "margin %": "Margin %", "margin": "Margin %", "margin percent": "Margin %",
    "discount": "Discount",
    "tax %": "Tax %", "gst %": "Tax %", "tax": "Tax %", "gst": "Tax %",
    "notes": "Notes", "remarks": "Notes",
}
for _col in HEADER_COLUMNS:
    HEADER_ALIASES.setdefault(_col.lower(), _col)

ITEM_ALIASES = {
    "estimate row #": "Estimate Row #", "estimate row": "Estimate Row #", "row #": "Estimate Row #",
    "estimate id": "Estimate ID", "estimate code": "Estimate ID",
    "product id": "Product ID", "product code": "Product ID",
    "description": "Description", "item": "Description", "item description": "Description",
    "category": "Category",
    "quantity": "Quantity", "qty": "Quantity",
    "unit": "Unit", "uom": "Unit",
    "rate": "Rate",
    "discount %": "Discount %", "discount": "Discount %",
    "tax %": "Tax %", "gst %": "Tax %", "tax": "Tax %", "gst": "Tax %",
}
for _col in ITEMS_COLUMNS:
    ITEM_ALIASES.setdefault(_col.lower(), _col)

# Estimate ID / Client Name / Client Phone are required on the header
# row (a header row with no client can't produce a usable Estimate);
# Margin %/Discount/Tax %/Valid Until/Notes are all optional and
# default sensibly during commit. Estimate ID itself is optional in the
# sense that BLANK is a valid value (spec section 16) - it's still
# listed as "required" here only so the column must be present in the
# uploaded file, not that every cell in it must be filled.
REQUIRED_HEADER_COLUMNS = ["Client Name", "Client Phone"]
REQUIRED_ITEM_COLUMNS = ["Estimate Row #", "Description", "Quantity", "Rate"]

# Whole-number UOMs (spec section 24) - Quantity must be an integer
# when the item's unit is one of these; other units (Sq Ft, Sq M, Kg,
# ...) may take decimals.
WHOLE_NUMBER_UNITS = {"nos", "piece", "pieces", "pcs", "set", "sets", "pair", "pairs"}

from app.shared.import_normalize import normalize_match_key, normalize_number, normalize_date, enforce_workbook_row_limit


# ---------------------------------------------------------------------------
# Template generation
# ---------------------------------------------------------------------------

EXAMPLE_HEADER_ROW = {
    "Estimate ID": "", "Client Name": "Priya Sharma", "Client Phone": "9827712345",
    "Estimate Date": "2026-08-23", "Valid Until": "2026-09-22",
    "Margin %": 15, "Discount": 0, "Tax %": 18, "Notes": "Living room + kitchen scope",
}

EXAMPLE_ITEM_ROWS = [
    {
        "Estimate Row #": 1, "Estimate ID": "", "Product ID": "PRD-014",
        "Description": "Custom Modular Kitchen - L Shape", "Category": "Material",
        "Quantity": 1, "Unit": "Set", "Rate": 185000, "Discount %": 0, "Tax %": 18,
    },
    {
        "Estimate Row #": 1, "Estimate ID": "", "Product ID": "PRD-021",
        "Description": "Site Installation & Fitting", "Category": "Labor",
        "Quantity": 6, "Unit": "Days", "Rate": 2500, "Discount %": 0, "Tax %": 18,
    },
]

TEMPLATE_VERSION = "1.0"


def build_import_template() -> BytesIO:
    """Two-sheet workbook - Estimate Header + Estimate Items - plus a
    third Instructions sheet (spec section 3), all through the shared
    write_sheet/Woodful branding helper. Deliberately NOT a third "Sample
    Data" sheet - the one sample estimate (row 1 on each data sheet,
    joined by Estimate Row # = 1) is real, realistic Woodful data the
    user overwrites, matching spec section 3's "no separate sample
    sheet, one realistic row" rule.
    """
    wb = Workbook()
    wb.remove(wb.active)

    write_sheet(
        wb, sheet_name="Estimate Header", title="Woodful Creations - Estimate Import Template",
        subtitle="One row per estimate. Leave Estimate ID blank to create a new estimate.",
        columns=HEADER_COLUMNS,
        headers=[c + " *" if c in REQUIRED_HEADER_COLUMNS else c for c in HEADER_COLUMNS],
        rows=[EXAMPLE_HEADER_ROW],
    )
    write_sheet(
        wb, sheet_name="Estimate Items", title="Woodful Creations - Estimate Items",
        subtitle="One row per line item. Estimate Row # links an item back to its header row (not a database ID).",
        columns=ITEMS_COLUMNS,
        headers=[c + " *" if c in REQUIRED_ITEM_COLUMNS else c for c in ITEMS_COLUMNS],
        rows=EXAMPLE_ITEM_ROWS,
    )

    instructions_rows = [
        {"Field": "Estimate ID", "Required": "No", "Description": "Blank = create new estimate. A valid existing Estimate code (e.g. EST-014) = update that estimate. Anything else is rejected.", "Expected Format / Allowed Values": "Blank, or an existing Estimate code", "Example": "EST-014 or blank"},
        {"Field": "Client Name", "Required": "Yes", "Description": "Must match an existing client together with Client Phone.", "Expected Format / Allowed Values": "Text", "Example": "Priya Sharma"},
        {"Field": "Client Phone", "Required": "Yes", "Description": "Must match the client's phone on file, together with Client Name.", "Expected Format / Allowed Values": "Digits, with or without spacing/punctuation", "Example": "98277 12345"},
        {"Field": "Estimate Date", "Required": "No", "Description": "Defaults to today if left blank.", "Expected Format / Allowed Values": "YYYY-MM-DD or DD-MM-YYYY", "Example": "2026-08-23"},
        {"Field": "Valid Until", "Required": "No", "Description": "Stored on the estimate and shown on the Estimate PDF.", "Expected Format / Allowed Values": "YYYY-MM-DD or DD-MM-YYYY", "Example": "2026-09-22"},
        {"Field": "Margin %", "Required": "No", "Description": "Estimate-level margin override.", "Expected Format / Allowed Values": "Number 0-100", "Example": "15"},
        {"Field": "Discount", "Required": "No", "Description": "Absolute currency amount, not a percent.", "Expected Format / Allowed Values": "Number >= 0", "Example": "0"},
        {"Field": "Tax %", "Required": "No", "Description": "Defaults to 18 if left blank.", "Expected Format / Allowed Values": "Number 0-100", "Example": "18"},
        {"Field": "Estimate Row #", "Required": "Yes (Items sheet)", "Description": "Groups item rows under one header row. Every item must reference a Row # that exists on the Header sheet.", "Expected Format / Allowed Values": "Whole number, unique per header row", "Example": "1"},
        {"Field": "Product ID", "Required": "Yes (Items sheet)", "Description": "Must be an existing Product code. Blank or unrecognized Product IDs are rejected - this import never creates a Product.", "Expected Format / Allowed Values": "Existing Product code", "Example": "PRD-014"},
        {"Field": "Quantity", "Required": "Yes (Items sheet)", "Description": "Whole numbers only when Unit is Nos/Piece/Set/Pair; decimals allowed for measurement units (Sq Ft, Kg, ...).", "Expected Format / Allowed Values": "Number > 0", "Example": "1"},
        {"Field": "Rate", "Required": "Yes (Items sheet)", "Description": "Per-unit rate before discount/tax.", "Expected Format / Allowed Values": "Number >= 0", "Example": "185000"},
    ]
    write_sheet(
        wb, sheet_name="Instructions", title="Woodful Estimate Import - Instructions",
        subtitle=f"Version: {TEMPLATE_VERSION}   |   * = Mandatory   |   A completely blank row is skipped; a partially filled row is reported as an error.",
        columns=["Field", "Required", "Description", "Expected Format / Allowed Values", "Example"],
        rows=instructions_rows,
    )
    try:
        wb["Instructions"].protection.sheet = True
    except Exception:
        pass

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_sheet(ws, all_columns, aliases, required_cols, sheet_label) -> List[dict]:
    header_row_idx = None
    col_index = None
    for row in ws.iter_rows(min_row=1, max_row=10):
        values = [c.value for c in row]
        resolved = resolve_header_row_with_aliases(values, aliases, required_cols)
        if resolved:
            header_row_idx = row[0].row
            col_index = resolved
            break
    if header_row_idx is None:
        raise ValueError(
            f"Couldn't find the expected column headers on the \"{sheet_label}\" sheet. "
            f"Please use the downloaded template, or make sure every required column "
            f"({', '.join(required_cols)}) has a recognizable header and isn't duplicated."
        )

    rows = []
    for row in ws.iter_rows(min_row=header_row_idx + 1):
        values = [c.value for c in row]
        # Blank row rule (spec section 4): a completely blank row never
        # stops the import - it's simply skipped. A partially filled row
        # is kept here and reported as a validation error downstream.
        if all(_clean(v) is None for v in values):
            continue
        rows.append({name: _clean(values[idx]) if idx < len(values) else None for name, idx in col_index.items()})
    return rows


def parse_uploaded_workbook(file_bytes: bytes) -> tuple:
    """Returns (header_rows, item_rows) - raw dicts, no validation/matching
    yet. Requires both an "Estimate Header" and an "Estimate Items" sheet
    (by name, falling back to worksheet position 1/2 for a workbook whose
    sheets were renamed but otherwise match the template)."""
    wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True)
    enforce_workbook_row_limit(wb)

    header_ws = wb["Estimate Header"] if "Estimate Header" in wb.sheetnames else wb.worksheets[0]
    items_ws = wb["Estimate Items"] if "Estimate Items" in wb.sheetnames else (
        wb.worksheets[1] if len(wb.worksheets) > 1 else None)
    if items_ws is None:
        raise ValueError('This workbook needs both an "Estimate Header" sheet and an "Estimate Items" sheet.')

    header_rows = _parse_sheet(header_ws, HEADER_COLUMNS, HEADER_ALIASES, REQUIRED_HEADER_COLUMNS, "Estimate Header")
    item_rows = _parse_sheet(items_ws, ITEMS_COLUMNS, ITEM_ALIASES, REQUIRED_ITEM_COLUMNS, "Estimate Items")
    return header_rows, item_rows


# ---------------------------------------------------------------------------
# Validation / matching
# ---------------------------------------------------------------------------

def validate_header_row(row: dict, row_number: int, db, estimates_by_code, clients_by_key):
    """Validates one Estimate Header row. Returns (result_dict, errors).
    Never writes anything."""
    errors = []

    estimate_ref = row.get("Estimate Row #")  # not present on header sheet; see items linkage below
    raw_estimate_id = row.get("Estimate ID")
    matched_estimate = None
    is_new = True
    if raw_estimate_id:
        matched_estimate = estimates_by_code.get(normalize_match_key(str(raw_estimate_id)))
        if not matched_estimate:
            errors.append(
                f'Estimate ID "{raw_estimate_id}" was not found. Leave Estimate ID blank to create a new '
                f'estimate, or use an existing Estimate code exactly as shown in the ERP.'
            )
        else:
            is_new = False

    client_name = row.get("Client Name")
    client_phone = row.get("Client Phone")
    if not client_name:
        errors.append("Client Name is required")
    if not client_phone:
        errors.append("Client Phone is required")

    matched_client = None
    if client_name and client_phone:
        key = (normalize_match_key(client_name), normalize_phone_key(client_phone))
        matched_client = clients_by_key.get(key)
        if not matched_client:
            errors.append(
                f'No existing client matches "{client_name}" / "{client_phone}" together. '
                f'Create the client first (Clients page or Client import), then re-upload.'
            )

    estimate_date = normalize_date(row.get("Estimate Date")) if row.get("Estimate Date") else None
    if row.get("Estimate Date") and estimate_date is None:
        errors.append(f"Estimate Date must be a recognizable date, got {row.get('Estimate Date')!r}")

    valid_until = normalize_date(row.get("Valid Until")) if row.get("Valid Until") else None
    if row.get("Valid Until") and valid_until is None:
        errors.append(f"Valid Until must be a recognizable date, got {row.get('Valid Until')!r}")

    margin_percent = None
    if row.get("Margin %") is not None:
        margin_percent = normalize_number(row["Margin %"])
        if margin_percent is None:
            errors.append(f"Invalid Margin %: {row['Margin %']!r}")

    discount = Decimal("0")
    if row.get("Discount") is not None:
        parsed = normalize_number(row["Discount"])
        if parsed is None:
            errors.append(f"Invalid Discount: {row['Discount']!r}")
        else:
            discount = parsed

    tax_percent = Decimal("18")
    if row.get("Tax %") is not None:
        parsed = normalize_number(row["Tax %"])
        if parsed is None:
            errors.append(f"Invalid Tax %: {row['Tax %']!r}")
        else:
            tax_percent = parsed

    result = {
        "row_number": row_number,
        "estimate_ref": estimate_ref,
        "raw_estimate_id": raw_estimate_id,
        "matched_estimate_id": matched_estimate.id if matched_estimate else None,
        "matched_estimate_code": matched_estimate.estimate_code if matched_estimate else None,
        "is_new_estimate": is_new,
        "client_name": client_name,
        "client_phone": client_phone,
        "matched_client_id": matched_client.id if matched_client else None,
        "estimate_date": estimate_date,
        "valid_until": valid_until,
        "margin_percent": margin_percent,
        "discount": discount,
        "tax_percent": tax_percent,
        "notes": row.get("Notes"),
    }
    return result, errors


def validate_item_row(row: dict, row_number: int, products_by_code):
    """Validates one Estimate Items row against a Product Master lookup
    keyed by Product ID (exact, case-insensitive) - never by name/
    description, per spec section 15."""
    errors = []

    estimate_ref_raw = row.get("Estimate Row #")
    estimate_ref = None
    if not estimate_ref_raw:
        errors.append("Estimate Row # is required")
    else:
        try:
            estimate_ref = int(Decimal(str(estimate_ref_raw)))
        except (InvalidOperation, ValueError):
            errors.append(f"Estimate Row # must be a whole number, got {estimate_ref_raw!r}")

    product_code = row.get("Product ID")
    matched_product = None
    if not product_code:
        errors.append("Product ID is required - this import never creates a Product automatically")
    else:
        matched_product = products_by_code.get(normalize_match_key(str(product_code)))
        if not matched_product:
            errors.append(
                f'Product ID "{product_code}" was not found. Create the product first, or correct the Product ID, then re-upload.'
            )

    description = row.get("Description")
    if not description:
        errors.append("Description is required")

    unit = (row.get("Unit") or (matched_product.unit if matched_product else None) or "Nos")

    quantity = None
    if row.get("Quantity") is None:
        errors.append("Quantity is required")
    else:
        quantity = normalize_number(row["Quantity"])
        if quantity is None:
            errors.append(f"Invalid Quantity: {row['Quantity']!r}")
        elif quantity <= 0:
            errors.append("Quantity must be greater than zero")
        elif unit.strip().lower() in WHOLE_NUMBER_UNITS and quantity != quantity.to_integral_value():
            errors.append(f'Quantity must be a whole number for unit "{unit}", got {quantity}')

    rate = None
    if row.get("Rate") is None:
        errors.append("Rate is required")
    else:
        rate = normalize_number(row["Rate"])
        if rate is None:
            errors.append(f"Invalid Rate: {row['Rate']!r}")
        elif rate < 0:
            errors.append("Rate cannot be negative")

    discount_percent = Decimal("0")
    if row.get("Discount %") is not None:
        parsed = normalize_number(row["Discount %"])
        if parsed is None:
            errors.append(f"Invalid Discount %: {row['Discount %']!r}")
        else:
            discount_percent = parsed

    tax_percent = None
    if row.get("Tax %") is not None:
        parsed = normalize_number(row["Tax %"])
        if parsed is None:
            errors.append(f"Invalid Tax %: {row['Tax %']!r}")
        else:
            tax_percent = parsed

    amount = None
    if quantity is not None and rate is not None:
        line = quantity * rate
        if discount_percent:
            line = line - (line * discount_percent / Decimal("100"))
        amount = line.quantize(Decimal("0.01"))

    result = {
        "row_number": row_number,
        "estimate_ref": estimate_ref,
        "product_id": matched_product.id if matched_product else None,
        "product_code": product_code,
        "description": description,
        "category": row.get("Category"),
        "quantity": quantity,
        "unit": unit,
        "rate": rate,
        "discount_percent": discount_percent,
        "tax_percent": tax_percent,
        "amount": amount,
    }
    return result, errors
