"""Excel import for the Product Master - same discipline as
app/modules/procurement/imports/purchase_import.py (one fixed template shared by the download
and the parser, never writes a parsed row directly to the database,
preview/commit are two separate steps). Kept as a distinct module
rather than folded into purchase_import.py since products and purchases
are unrelated entities with an unrelated column set.
"""
from io import BytesIO
from typing import List, Optional

import openpyxl
from openpyxl import Workbook

from app.shared.exporters import write_sheet, write_instructions_sheet
from app.shared.import_common import _clean, resolve_header_row_bare

TEMPLATE_VERSION = "2.0"  # bumped: adds Instructions sheet + possible-match handling

PRODUCT_IMPORT_COLUMNS = [
    "Product Name *", "Type", "Category", "Subcategory", "Unit *",
    "Length", "Width", "Height", "Dimension Unit",
    "Primary Material", "Finish",
    "Material Cost", "Hardware Cost", "Labour Cost", "Machine Cost",
    "Finish Cost", "Packing Cost", "Transport Cost", "Other Cost",
    "Overhead %", "Margin %", "Cost Price", "Selling Price", "Notes",
]

HEADER_ALIASES = {
    "product": "Product Name *",
    "product name": "Product Name *",
    "name": "Product Name *",
    "type": "Type",
    "product type": "Type",
    "category": "Category",
    "subcategory": "Subcategory",
    "sub category": "Subcategory",
    "unit": "Unit *",
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
    "default rate": "Selling Price",  # matches the Product export's own column header exactly - Export -> Edit -> Re-import must round-trip without silently losing this field
    "price": "Selling Price",
    "notes": "Notes",
    "remarks": "Notes",
}
for _col in PRODUCT_IMPORT_COLUMNS:
    HEADER_ALIASES.setdefault(_col.lower(), _col)
    HEADER_ALIASES.setdefault(_col.rstrip(" *").lower(), _col)


# Only Product Name and Unit are hard requirements - everything else on
# a product is genuinely optional, unlike the purchase import's tighter
# required set.
REQUIRED_COLUMNS = ["Product Name *", "Unit *"]


from app.shared.import_normalize import normalize_match_key, normalize_number, enforce_workbook_row_limit


EXAMPLE_ROWS = [
    {
        "Product Name *": "Custom Walk-in Wardrobe", "Type": "custom", "Category": "Furniture",
        "Subcategory": "Wardrobes", "Unit *": "Nos", "Length": 120, "Width": 24, "Height": 96,
        "Dimension Unit": "in", "Primary Material": "BWP Plywood + laminate", "Finish": "Matte laminate",
        "Material Cost": 55000, "Hardware Cost": 8000, "Labour Cost": 15000, "Machine Cost": 3000,
        "Finish Cost": 2500, "Packing Cost": 1000, "Transport Cost": 1500, "Other Cost": 500,
        "Overhead %": 8, "Margin %": 25, "Cost Price": 85000, "Selling Price": 125000,
        "Notes": "Sample row - delete before uploading your real data",
    },
    {
        "Product Name *": "CNC Fluted Wall Panel", "Type": "standard", "Category": "CNC Services",
        "Subcategory": "CNC Routing", "Unit *": "Sq Ft", "Length": None, "Width": None, "Height": None,
        "Dimension Unit": "in", "Primary Material": "MDF", "Finish": "Natural / painted",
        "Material Cost": 90, "Hardware Cost": 0, "Labour Cost": 40, "Machine Cost": 35,
        "Finish Cost": 15, "Packing Cost": 5, "Transport Cost": 5, "Other Cost": 0,
        "Overhead %": 8, "Margin %": 30, "Cost Price": 190, "Selling Price": 271,
        "Notes": "Sample row - priced per Sq Ft; delete before uploading your real data",
    },
]

PRODUCT_FIELD_DOCS = [
    {"name": "Product Name *", "mandatory": True, "meaning": "Full name of the product or service, as it should appear on Estimates/Orders.",
     "format": "Free text."},
    {"name": "Type", "mandatory": False, "meaning": "Whether this is a standard catalog item or a one-off custom build.",
     "format": "Must match exactly.", "accepted_values": ["standard", "custom"]},
    {"name": "Category", "mandatory": False, "meaning": "Top-level grouping (e.g. Furniture, CNC Services, Laser Services, Gift Items).",
     "format": "Free text - use the same values as the Product form's Category field."},
    {"name": "Subcategory", "mandatory": False, "meaning": "More specific grouping within the category.", "format": "Free text."},
    {"name": "Unit *", "mandatory": True, "meaning": "The unit this product is priced/sold in.",
     "format": "Free text, e.g. Nos, Sq Ft, Set, Pair."},
    {"name": "Length / Width / Height", "mandatory": False, "meaning": "Physical dimensions, where applicable.", "format": "Number."},
    {"name": "Dimension Unit", "mandatory": False, "meaning": "Unit the Length/Width/Height are measured in.", "format": "e.g. in, cm, ft."},
    {"name": "Primary Material", "mandatory": False, "meaning": "Main material used.", "format": "Free text."},
    {"name": "Finish", "mandatory": False, "meaning": "Surface finish.", "format": "Free text."},
    {"name": "Material/Hardware/Labour/Machine/Finish/Packing/Transport/Other Cost", "mandatory": False,
     "meaning": "Internal cost components (Woodful Internal Cost) - never shown to customers.", "format": "Number, in Rs."},
    {"name": "Overhead %", "mandatory": False, "meaning": "Overhead allocation applied on top of direct costs.", "format": "Number, e.g. 8 for 8%."},
    {"name": "Margin %", "mandatory": False,
     "meaning": "Woodful's target margin - used to suggest a selling price (Selling Price = Cost / (1 - Margin%)). Does not by itself set Selling Price.",
     "format": "Number, e.g. 25 for 25%."},
    {"name": "Cost Price", "mandatory": False, "meaning": "Total internal cost, if known directly rather than built up from the cost columns.", "format": "Number, in Rs."},
    {"name": "Selling Price", "mandatory": False,
     "meaning": "Woodful Selling Rate - what is actually charged. A market/reference rate is never automatically the selling price; this is Woodful's own chosen rate.",
     "format": "Number, in Rs."},
    {"name": "Notes", "mandatory": False, "meaning": "Any other remarks.", "format": "Free text."},
]


def build_import_template() -> BytesIO:
    wb = Workbook()
    wb.remove(wb.active)
    write_sheet(
        wb, sheet_name="Product Data", title="Woodful Creations - Product Import Template",
        subtitle="Product Name and Unit are required for every row (marked with *). Type must be 'standard' or "
                  "'custom'. Product ID is generated automatically - do not add a Product ID column. "
                  "Do not change the column headers.",
        columns=PRODUCT_IMPORT_COLUMNS, rows=EXAMPLE_ROWS,
    )
    write_instructions_sheet(
        wb, template_name="Woodful Product Import Template", version=TEMPLATE_VERSION,
        field_docs=PRODUCT_FIELD_DOCS,
        id_rule="Product ID is system-generated and never typed in by hand. Leave any ID column out entirely - "
                "there is none in this template.",
        duplicate_rule="A row is only treated as an existing product if its name matches an existing active "
                        "product exactly - it will be reused, not re-created. A row whose name closely resembles "
                        "(but doesn't exactly match) an existing product is flagged as a possible match during "
                        "preview; you will be asked to confirm whether to use the existing product or create a "
                        "new one. Nothing is merged or created automatically on a possible match.",
        extra_notes=[
            "A completely blank row is skipped. A row with only some fields filled in is still validated - "
            "if Product Name or Unit is missing, that row will show an error.",
            "Internal cost fields and Margin % are never shown to customers and only affect Woodful's own "
            "records - they never automatically change the customer-facing Selling Price.",
        ],
    )
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def parse_uploaded_workbook(file_bytes: bytes) -> List[dict]:
    wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True)
    enforce_workbook_row_limit(wb)
    ws = wb.worksheets[0]

    header_row_idx = None
    col_index = None
    for row in ws.iter_rows(min_row=1, max_row=10):
        values = [c.value for c in row]
        resolved = resolve_header_row_bare(values, HEADER_ALIASES, REQUIRED_COLUMNS)
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


def validate_and_match_row(row: dict, existing_by_name: dict, fuzzy_candidates: Optional[list] = None):
    """Validates one parsed row and checks whether a product with this
    name already exists (case-insensitive exact match - reused, not
    re-created), and, when fuzzy_candidates is supplied, flags a
    "possible match" typo/near-match nudge using
    the exact same shared logic as the Product UI's own duplicate check
    (see app.modules.clients.matching.find_fuzzy_name_matches, reused here
    rather than reimplemented so the UI and Excel import can never
    silently disagree about what counts as a possible match). Never
    writes anything."""
    errors = []
    name = row.get("Product Name *")
    if not name:
        errors.append("Product Name is required")

    product_type = (row.get("Type") or "standard").strip().lower() if row.get("Type") else "standard"
    if product_type not in VALID_PRODUCT_TYPES:
        errors.append(f"Type must be 'standard' or 'custom' (got {row.get('Type')!r})")

    unit = row.get("Unit *") or "Nos"

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

    # Same domain rules ProductCreate/ProductUpdate enforce on the normal
    # API - the import path must not be a way to slip an invalid product
    # past validation that the UI/API would otherwise reject.
    for label, value in (
        ("Material Cost", material_cost), ("Hardware Cost", hardware_cost),
        ("Labour Cost", labour_cost), ("Machine Cost", machine_cost),
        ("Finish Cost", finish_cost), ("Packing Cost", packing_cost),
        ("Transport Cost", transport_cost), ("Other Cost", other_cost),
        ("Cost Price", cost_price), ("Selling Price", selling_price),
    ):
        if value is not None and value < 0:
            errors.append(f"{label} cannot be negative")
    if overhead_percent is not None and overhead_percent < 0:
        errors.append("Overhead % cannot be negative")
    if margin_percent is not None and margin_percent >= 100:
        errors.append("Margin % must be less than 100")

    matched = existing_by_name.get(normalize_match_key(name)) if name else None

    possible_match = None
    if not matched and name and fuzzy_candidates is not None:
        from app.modules.clients.matching import find_fuzzy_name_matches
        fuzzy_hits = find_fuzzy_name_matches(db=None, name=name, candidates=fuzzy_candidates, limit=1)
        possible_match = fuzzy_hits[0] if fuzzy_hits else None

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
        "possible_match_product_id": possible_match.id if possible_match else None,
        "possible_match_name": possible_match.name if possible_match else None,
    }
    return result, errors
