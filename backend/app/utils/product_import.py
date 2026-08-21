"""Excel import for the Product Master - same discipline as
app/utils/purchase_import.py (one fixed template shared by the download
and the parser, never writes a parsed row directly to the database,
preview/commit are two separate steps). Kept as a distinct module
rather than folded into purchase_import.py since products and purchases
are unrelated entities with an unrelated column set.
"""
import re
from io import BytesIO
from decimal import Decimal, InvalidOperation
from typing import List, Optional

import openpyxl
from openpyxl import Workbook

from app.utils.exporters import write_sheet

PRODUCT_IMPORT_COLUMNS = [
    "Product Name", "Type", "Category", "Subcategory", "Unit",
    "Length", "Width", "Height", "Dimension Unit",
    "Primary Material", "Finish",
    "Material Cost", "Hardware Cost", "Labour Cost", "Machine Cost",
    "Finish Cost", "Packing Cost", "Transport Cost", "Other Cost",
    "Overhead %", "Margin %", "Cost Price", "Selling Price", "Notes",
]

HEADER_ALIASES = {
    "product": "Product Name",
    "product name": "Product Name",
    "name": "Product Name",
    "type": "Type",
    "product type": "Type",
    "category": "Category",
    "subcategory": "Subcategory",
    "sub category": "Subcategory",
    "unit": "Unit",
    "length": "Length",
    "width": "Width",
    "height": "Height",
    "dimension unit": "Dimension Unit",
    "dim unit": "Dimension Unit",
    "primary material": "Primary Material",
    "material": "Primary Material",
    "finish": "Finish",
    "material cost": "Material Cost",
    "hardware cost": "Hardware Cost",
    "labour cost": "Labour Cost",
    "labor cost": "Labour Cost",
    "machine cost": "Machine Cost",
    "finish cost": "Finish Cost",
    "packing cost": "Packing Cost",
    "transport cost": "Transport Cost",
    "other cost": "Other Cost",
    "overhead %": "Overhead %",
    "overhead percent": "Overhead %",
    "margin %": "Margin %",
    "margin percent": "Margin %",
    "cost price": "Cost Price",
    "cost": "Cost Price",
    "selling price": "Selling Price",
    "price": "Selling Price",
    "notes": "Notes",
    "remarks": "Notes",
}
for _col in PRODUCT_IMPORT_COLUMNS:
    HEADER_ALIASES.setdefault(_col.lower(), _col)


def _normalize_header_cell(raw) -> Optional[str]:
    if raw is None:
        return None
    key = re.sub(r"\s+", " ", str(raw).strip().lower())
    return HEADER_ALIASES.get(key)


# Only Product Name and Unit are hard requirements - everything else on
# a product is genuinely optional, unlike the purchase import's tighter
# required set.
REQUIRED_COLUMNS = ["Product Name", "Unit"]


def _resolve_header_row(values) -> Optional[dict]:
    resolved = {}
    for idx, raw in enumerate(values):
        canonical = _normalize_header_cell(raw)
        if canonical is None:
            continue
        if canonical in resolved:
            return None
        resolved[canonical] = idx
    if all(col in resolved for col in REQUIRED_COLUMNS):
        return resolved
    return None


_NUMERIC_NOISE_RE = re.compile(r"[₹$€£%,\s]")


def normalize_number(raw) -> Optional[Decimal]:
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


def normalize_match_key(name: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


EXAMPLE_ROWS = [
    {
        "Product Name": "Harbor 3-Seater Sofa", "Type": "standard", "Category": "Seating", "Subcategory": "Sofas",
        "Unit": "Nos", "Length": 84, "Width": 36, "Height": 32, "Dimension Unit": "in",
        "Primary Material": "Teak frame + linen upholstery", "Finish": "Natural teak",
        "Material Cost": 18000, "Hardware Cost": 2500, "Labour Cost": 6000, "Machine Cost": 1200,
        "Finish Cost": 2000, "Packing Cost": 800, "Transport Cost": 1000, "Other Cost": 500,
        "Overhead %": 8, "Margin %": 30, "Cost Price": 32000, "Selling Price": 48000,
        "Notes": "Best seller, kept in standard catalog",
    },
    {
        "Product Name": "Custom Walk-in Wardrobe - Reference Build", "Type": "custom", "Category": "Storage",
        "Subcategory": "Wardrobes", "Unit": "Nos", "Length": 120, "Width": 24, "Height": 96,
        "Dimension Unit": "in", "Primary Material": "BWP Plywood + laminate", "Finish": "Matte laminate",
        "Material Cost": 55000, "Hardware Cost": 8000, "Labour Cost": 15000, "Machine Cost": 3000,
        "Finish Cost": 2500, "Packing Cost": 1000, "Transport Cost": 1500, "Other Cost": 500,
        "Overhead %": 8, "Margin %": 25, "Cost Price": 85000, "Selling Price": 125000,
        "Notes": "Client-specific, created from an approved estimate",
    },
]


def build_import_template() -> BytesIO:
    wb = Workbook()
    wb.remove(wb.active)
    write_sheet(
        wb, sheet_name="Product Import", title="Woodful Creations - Product Import Template",
        subtitle="Fill in one row per product. Type must be 'standard' or 'custom'. Do not change the column headers.",
        columns=PRODUCT_IMPORT_COLUMNS, rows=EXAMPLE_ROWS,
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
            "Please use the downloaded template, or make sure Product Name and Unit "
            "have a recognizable header and aren't duplicated."
        )

    rows = []
    for row in ws.iter_rows(min_row=header_row_idx + 1):
        values = [c.value for c in row]
        if all(_clean(v) is None for v in values):
            continue
        rows.append({name: _clean(values[idx]) if idx < len(values) else None for name, idx in col_index.items()})
    return rows


VALID_PRODUCT_TYPES = {"standard", "custom"}


def validate_and_match_row(row: dict, existing_by_name: dict):
    """Validates one parsed row and checks whether a product with this
    name already exists (case-insensitive exact match, never fuzzy -
    same standing principle as the purchase import). Returns
    (result_dict, errors_list); never writes anything."""
    errors = []
    name = row.get("Product Name")
    if not name:
        errors.append("Product Name is required")

    product_type = (row.get("Type") or "standard").strip().lower() if row.get("Type") else "standard"
    if product_type not in VALID_PRODUCT_TYPES:
        errors.append(f"Type must be 'standard' or 'custom' (got {row.get('Type')!r})")

    unit = row.get("Unit") or "Nos"

    def _num(col):
        raw = row.get(col)
        if raw is None:
            return None, None
        val = normalize_number(raw)
        if val is None:
            return None, f"Invalid {col}: {raw!r}"
        return val, None

    length, e1 = _num("Length")
    width, e2 = _num("Width")
    height, e3 = _num("Height")
    material_cost, e4 = _num("Material Cost")
    hardware_cost, e5 = _num("Hardware Cost")
    labour_cost, e6 = _num("Labour Cost")
    machine_cost, e7 = _num("Machine Cost")
    finish_cost, e8 = _num("Finish Cost")
    packing_cost, e9 = _num("Packing Cost")
    transport_cost, e10 = _num("Transport Cost")
    other_cost, e11 = _num("Other Cost")
    overhead_percent, e12 = _num("Overhead %")
    margin_percent, e13 = _num("Margin %")
    cost_price, e14 = _num("Cost Price")
    selling_price, e15 = _num("Selling Price")
    for e in (e1, e2, e3, e4, e5, e6, e7, e8, e9, e10, e11, e12, e13, e14, e15):
        if e:
            errors.append(e)

    matched = existing_by_name.get(normalize_match_key(name)) if name else None

    result = {
        "name": name, "product_type": product_type, "category": row.get("Category"),
        "subcategory": row.get("Subcategory"), "unit": unit,
        "length": length, "width": width, "height": height,
        "dimension_unit": row.get("Dimension Unit") or "in",
        "primary_material": row.get("Primary Material"), "finish": row.get("Finish"),
        "material_cost": material_cost, "hardware_cost": hardware_cost, "labour_cost": labour_cost,
        "machine_cost": machine_cost, "finish_cost": finish_cost, "packing_cost": packing_cost,
        "transport_cost": transport_cost, "other_cost": other_cost,
        "overhead_percent": overhead_percent, "margin_percent": margin_percent,
        "cost_price": cost_price, "selling_price": selling_price, "notes": row.get("Notes"),
        "matched_product_id": matched.id if matched else None,
        "is_duplicate": matched is not None,
    }
    return result, errors
