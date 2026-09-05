"""Excel import for Orders - the first
Order import implementation; none existed before this.

Deliberately mirrors app/utils/estimate_import.py line for line wherever
the two entities share the same rule, rather than inventing a second
way to express "blank row skipped", "ID blank/valid/unknown", "Product
ID authoritative", etc. - see that module's docstring for the shared
reasoning. This docstring only calls out what's different for Orders.

Differences from Estimate import:

1. Order Header may optionally reference an Estimate ID (spec section
   17). When given and valid, commit() converts that Estimate into this
   Order exactly the way POST /api/orders/ already does when created
   from the UI with from_estimate_id set (same guardrails: estimate
   must be "approved", and not already converted) - so an
   Excel-imported conversion is indistinguishable from a UI-driven one.
   A blank Estimate ID just creates a standalone order.

2. Two Order Header fields the spec text lists - "Payment Terms" - do
   not exist on the Order model/UI today (there is no payment_terms
   column). Per the master rule (spec section 1: "do not create
   Excel-only fields... if a field is required but doesn't exist,
   add it to the backend/UI first"), that column is deliberately left
   out of this template rather than added as an Excel-only field with
   nothing behind it. It needs its own migration + UI change before an
   Order Excel column can honestly represent it - flagged here, not
   silently dropped.

3. Orders don't have Estimate's clean single set of "finalized"
   statuses - see ORDER_LOCKED_STATUSES below for the (narrower,
   locally-scoped) rule this import uses to refuse editing a
   Completed/Cancelled order by re-import.
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
    "Order ID", "Client Name", "Client Phone", "Estimate ID",
    "Order Date", "Expected Delivery Date", "Discount", "Tax %", "Notes",
]

ITEMS_COLUMNS = [
    "Order Row #", "Order ID", "Product ID", "Description",
    "Category", "Quantity", "Unit", "Rate", "Discount %", "Tax %",
]

HEADER_ALIASES = {
    "order id": "Order ID", "order code": "Order ID", "id": "Order ID",
    "client name": "Client Name", "client": "Client Name",
    "client phone": "Client Phone", "phone": "Client Phone",
    "estimate id": "Estimate ID", "estimate code": "Estimate ID", "estimate": "Estimate ID",
    "order date": "Order Date", "date": "Order Date",
    "expected delivery date": "Expected Delivery Date", "delivery date": "Expected Delivery Date",
    "discount": "Discount",
    "tax %": "Tax %", "gst %": "Tax %", "tax": "Tax %", "gst": "Tax %",
    "notes": "Notes", "remarks": "Notes",
}
for _col in HEADER_COLUMNS:
    HEADER_ALIASES.setdefault(_col.lower(), _col)

ITEM_ALIASES = {
    "order row #": "Order Row #", "order row": "Order Row #", "row #": "Order Row #",
    "order id": "Order ID", "order code": "Order ID",
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

REQUIRED_HEADER_COLUMNS = ["Client Name", "Client Phone"]
REQUIRED_ITEM_COLUMNS = ["Order Row #", "Description", "Quantity", "Rate"]

WHOLE_NUMBER_UNITS = {"nos", "piece", "pieces", "pcs", "set", "sets", "pair", "pairs"}

# A narrower, locally-scoped rule (see module docstring point 3) - Orders
# don't have an Estimate-style single "finalized" concept in
# status_rules.py today, so this import defines its own minimal
# protection rather than overloading that shared file with an
# import-specific rule: an order already Completed or Cancelled is a
# closed record and should go through the normal Order edit screen
# (with its own audit trail) if it genuinely needs to change, not be
# silently rewritten by a bulk re-import.
ORDER_LOCKED_STATUSES = {"Completed", "Cancelled"}

from app.shared.import_normalize import normalize_match_key, normalize_number, normalize_date, enforce_workbook_row_limit


# ---------------------------------------------------------------------------
# Template generation
# ---------------------------------------------------------------------------

EXAMPLE_HEADER_ROW = {
    "Order ID": "", "Client Name": "Priya Sharma", "Client Phone": "9827712345",
    "Estimate ID": "", "Order Date": "2026-08-23", "Expected Delivery Date": "2026-10-15",
    "Discount": 0, "Tax %": 18, "Notes": "Living room + kitchen scope",
}

EXAMPLE_ITEM_ROWS = [
    {
        "Order Row #": 1, "Order ID": "", "Product ID": "PRD-014",
        "Description": "Custom Modular Kitchen - L Shape", "Category": "Material",
        "Quantity": 1, "Unit": "Set", "Rate": 185000, "Discount %": 0, "Tax %": 18,
    },
    {
        "Order Row #": 1, "Order ID": "", "Product ID": "PRD-021",
        "Description": "Site Installation & Fitting", "Category": "Labor",
        "Quantity": 6, "Unit": "Days", "Rate": 2500, "Discount %": 0, "Tax %": 18,
    },
]

TEMPLATE_VERSION = "1.0"


def build_import_template() -> BytesIO:
    wb = Workbook()
    wb.remove(wb.active)

    write_sheet(
        wb, sheet_name="Order Header", title="Woodful Creations - Order Import Template",
        subtitle="One row per order. Leave Order ID blank to create a new order. "
                  "Set Estimate ID to convert that (approved) estimate into this order.",
        columns=HEADER_COLUMNS,
        headers=[c + " *" if c in REQUIRED_HEADER_COLUMNS else c for c in HEADER_COLUMNS],
        rows=[EXAMPLE_HEADER_ROW],
    )
    write_sheet(
        wb, sheet_name="Order Items", title="Woodful Creations - Order Items",
        subtitle="One row per line item. Order Row # links an item back to its header row (not a database ID). "
                  "Leave Order Items sheet rows out entirely for an order converted from an Estimate - "
                  "its items are copied from the Estimate automatically.",
        columns=ITEMS_COLUMNS,
        headers=[c + " *" if c in REQUIRED_ITEM_COLUMNS else c for c in ITEMS_COLUMNS],
        rows=EXAMPLE_ITEM_ROWS,
    )

    instructions_rows = [
        {"Field": "Order ID", "Required": "No", "Description": "Blank = create new order. A valid existing Order code (e.g. WC-2026-014) = update that order. Anything else is rejected.", "Expected Format / Allowed Values": "Blank, or an existing Order code", "Example": "WC-2026-014 or blank"},
        {"Field": "Client Name", "Required": "Yes", "Description": "Must match an existing client together with Client Phone.", "Expected Format / Allowed Values": "Text", "Example": "Priya Sharma"},
        {"Field": "Client Phone", "Required": "Yes", "Description": "Must match the client's phone on file, together with Client Name.", "Expected Format / Allowed Values": "Digits, with or without spacing/punctuation", "Example": "98277 12345"},
        {"Field": "Estimate ID", "Required": "No", "Description": "If set, converts that estimate into this order (estimate must be Approved and not already converted) and copies its line items - leave the Order Items sheet blank for this order in that case.", "Expected Format / Allowed Values": "Blank, or an existing, Approved, unconverted Estimate code", "Example": "EST-014 or blank"},
        {"Field": "Order Date", "Required": "No", "Description": "Defaults to today if left blank.", "Expected Format / Allowed Values": "YYYY-MM-DD or DD-MM-YYYY", "Example": "2026-08-23"},
        {"Field": "Expected Delivery Date", "Required": "No", "Description": "Stored on the order.", "Expected Format / Allowed Values": "YYYY-MM-DD or DD-MM-YYYY", "Example": "2026-10-15"},
        {"Field": "Discount", "Required": "No", "Description": "Absolute currency amount, not a percent. Ignored (inherited from the Estimate) when converting from an Estimate ID.", "Expected Format / Allowed Values": "Number >= 0", "Example": "0"},
        {"Field": "Tax %", "Required": "No", "Description": "Defaults to 18 if left blank. Ignored (inherited from the Estimate) when converting from an Estimate ID.", "Expected Format / Allowed Values": "Number 0-100", "Example": "18"},
        {"Field": "Order Row #", "Required": "Yes (Items sheet)", "Description": "Groups item rows under one header row. Not used at all for an order converted from an Estimate.", "Expected Format / Allowed Values": "Whole number, unique per header row", "Example": "1"},
        {"Field": "Product ID", "Required": "Yes (Items sheet)", "Description": "Must be an existing Product code. Blank or unrecognized Product IDs are rejected - this import never creates a Product.", "Expected Format / Allowed Values": "Existing Product code", "Example": "PRD-014"},
        {"Field": "Quantity", "Required": "Yes (Items sheet)", "Description": "Whole numbers only when Unit is Nos/Piece/Set/Pair; decimals allowed for measurement units (Sq Ft, Kg, ...).", "Expected Format / Allowed Values": "Number > 0", "Example": "1"},
        {"Field": "Rate", "Required": "Yes (Items sheet)", "Description": "Per-unit rate before discount/tax.", "Expected Format / Allowed Values": "Number >= 0", "Example": "185000"},
        {"Field": "(note)", "Required": "-", "Description": "\"Payment Terms\" is not yet a field on the Order Master in this ERP, so it is intentionally not a column here - adding it requires a backend/UI change first, not an Excel-only column.", "Expected Format / Allowed Values": "-", "Example": "-"},
    ]
    write_sheet(
        wb, sheet_name="Instructions", title="Woodful Order Import - Instructions",
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

def _parse_sheet(ws, aliases, required_cols, sheet_label) -> List[dict]:
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
        if all(_clean(v) is None for v in values):
            continue  # blank row rule (spec section 4) - never stops the import
        rows.append({name: _clean(values[idx]) if idx < len(values) else None for name, idx in col_index.items()})
    return rows


def parse_uploaded_workbook(file_bytes: bytes) -> tuple:
    """Returns (header_rows, item_rows). An "Order Items" sheet with zero
    data rows is valid (an order entirely converted from an Estimate
    needs none) - only a missing SHEET is an error."""
    wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True)
    enforce_workbook_row_limit(wb)

    header_ws = wb["Order Header"] if "Order Header" in wb.sheetnames else wb.worksheets[0]
    items_ws = wb["Order Items"] if "Order Items" in wb.sheetnames else (
        wb.worksheets[1] if len(wb.worksheets) > 1 else None)
    if items_ws is None:
        raise ValueError('This workbook needs both an "Order Header" sheet and an "Order Items" sheet.')

    header_rows = _parse_sheet(header_ws, HEADER_ALIASES, REQUIRED_HEADER_COLUMNS, "Order Header")
    try:
        item_rows = _parse_sheet(items_ws, ITEM_ALIASES, REQUIRED_ITEM_COLUMNS, "Order Items")
    except ValueError:
        # A blank Order Items sheet (headers present, zero data rows) is
        # fine when every order on the Header sheet converts from an
        # Estimate; whether that's actually true is checked per-order in
        # validate_header_row, not here.
        item_rows = []
    return header_rows, item_rows


# ---------------------------------------------------------------------------
# Validation / matching
# ---------------------------------------------------------------------------

def validate_header_row(row: dict, row_number: int, orders_by_code, clients_by_key, estimates_by_code):
    errors = []

    raw_order_id = row.get("Order ID")
    matched_order = None
    is_new = True
    if raw_order_id:
        matched_order = orders_by_code.get(normalize_match_key(str(raw_order_id)))
        if not matched_order:
            errors.append(
                f'Order ID "{raw_order_id}" was not found. Leave Order ID blank to create a new order, '
                f'or use an existing Order code exactly as shown in the ERP.'
            )
        else:
            is_new = False
            if matched_order.project_status in ORDER_LOCKED_STATUSES:
                errors.append(
                    f'Order {matched_order.order_code} is "{matched_order.project_status}" and can no longer be '
                    f'edited by re-import - use the Order edit screen if it genuinely needs to change.'
                )

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
                f'Create the client first, then re-upload.'
            )

    raw_estimate_id = row.get("Estimate ID")
    matched_estimate = None
    if raw_estimate_id:
        matched_estimate = estimates_by_code.get(normalize_match_key(str(raw_estimate_id)))
        if not matched_estimate:
            errors.append(f'Estimate ID "{raw_estimate_id}" was not found.')
        else:
            if matched_estimate.status != "approved":
                errors.append(
                    f'Estimate {matched_estimate.estimate_code} is "{matched_estimate.status}", not "approved" - '
                    f'only an approved estimate can be converted into an order.'
                )
            if matched_estimate.order_id:
                errors.append(f'Estimate {matched_estimate.estimate_code} has already been converted to an order.')

    order_date = normalize_date(row.get("Order Date")) if row.get("Order Date") else None
    if row.get("Order Date") and order_date is None:
        errors.append(f"Order Date must be a recognizable date, got {row.get('Order Date')!r}")

    delivery_date = normalize_date(row.get("Expected Delivery Date")) if row.get("Expected Delivery Date") else None
    if row.get("Expected Delivery Date") and delivery_date is None:
        errors.append(f"Expected Delivery Date must be a recognizable date, got {row.get('Expected Delivery Date')!r}")

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
        "raw_order_id": raw_order_id,
        "matched_order_id": matched_order.id if matched_order else None,
        "matched_order_code": matched_order.order_code if matched_order else None,
        "is_new_order": is_new,
        "client_name": client_name,
        "client_phone": client_phone,
        "matched_client_id": matched_client.id if matched_client else None,
        "raw_estimate_id": raw_estimate_id,
        "matched_estimate_id": matched_estimate.id if matched_estimate else None,
        "matched_estimate_code": matched_estimate.estimate_code if matched_estimate else None,
        "order_date": order_date,
        "delivery_date": delivery_date,
        "discount": discount,
        "tax_percent": tax_percent,
        "notes": row.get("Notes"),
    }
    return result, errors


def validate_item_row(row: dict, row_number: int, products_by_code):
    """Identical rule set to estimate_import.validate_item_row - see
    that module for the reasoning behind each check."""
    errors = []

    order_ref_raw = row.get("Order Row #")
    order_ref = None
    if not order_ref_raw:
        errors.append("Order Row # is required")
    else:
        try:
            order_ref = int(Decimal(str(order_ref_raw)))
        except (InvalidOperation, ValueError):
            errors.append(f"Order Row # must be a whole number, got {order_ref_raw!r}")

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
        "order_ref": order_ref,
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
