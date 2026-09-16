"""Catalog import processing: product and rate-card Excel import
schemas and parse/validate/commit logic. Combines the former
product_schemas.py, product_import.py, rate_card_schemas.py, and
rate_card_import.py."""
from pydantic import BaseModel, field_validator
from typing import Optional, List
from decimal import Decimal
from io import BytesIO
from typing import List, Optional
import openpyxl
from openpyxl import Workbook
from app.shared import write_sheet, write_instructions_sheet
from app.shared_imports import _clean, resolve_header_row_bare
from app.shared_imports import normalize_match_key, normalize_number, enforce_workbook_row_limit
from pydantic import BaseModel, field_validator, model_validator
from app.modules.catalog.models import uom_allowed_for_category, _validate_uom, _validate_source_type, _validate_confidence, _validate_margin_under_100, _validate_rate_field_not_negative
from app.shared import write_sheet
from app.modules.catalog.models import RATE_SOURCE_TYPES, RATE_CONFIDENCE_LEVELS, STANDARD_UOMS, uom_allowed_for_category
from app.shared_imports import normalize_number, enforce_workbook_row_limit


# --- product_schemas.py ---
class ProductImportRowPreview(BaseModel):
    row_number: int
    name: Optional[str] = None
    product_type: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    unit: Optional[str] = None
    length: Optional[Decimal] = None
    width: Optional[Decimal] = None
    height: Optional[Decimal] = None
    dimension_unit: Optional[str] = None
    primary_material: Optional[str] = None
    finish: Optional[str] = None
    material_cost: Optional[Decimal] = None
    hardware_cost: Optional[Decimal] = None
    labour_cost: Optional[Decimal] = None
    machine_cost: Optional[Decimal] = None
    finish_cost: Optional[Decimal] = None
    packing_cost: Optional[Decimal] = None
    transport_cost: Optional[Decimal] = None
    other_cost: Optional[Decimal] = None
    overhead_percent: Optional[Decimal] = None
    margin_percent: Optional[Decimal] = None
    cost_price: Optional[Decimal] = None
    selling_price: Optional[Decimal] = None
    notes: Optional[str] = None
    matched_product_id: Optional[int] = None
    is_duplicate: bool = False
    possible_match_product_id: Optional[int] = None
    possible_match_name: Optional[str] = None
    errors: List[str] = []


class ProductImportPreviewResponse(BaseModel):
    total_rows: int
    new_rows: int
    duplicate_rows: int
    error_rows: int
    rows: List[ProductImportRowPreview]


class ProductImportCommitRow(BaseModel):
    """Echoes one reviewed row back for actual creation. A row flagged
    as a duplicate on preview is only created if the caller explicitly
    confirms skip_duplicate_check=False for it - never silently
    creating a second product with the same name."""
    name: str
    product_type: str = "standard"
    category: Optional[str] = None
    subcategory: Optional[str] = None
    unit: str = "Nos"
    length: Optional[Decimal] = None
    width: Optional[Decimal] = None
    height: Optional[Decimal] = None
    dimension_unit: Optional[str] = "in"
    primary_material: Optional[str] = None
    finish: Optional[str] = None
    material_cost: Optional[Decimal] = None
    hardware_cost: Optional[Decimal] = None
    labour_cost: Optional[Decimal] = None
    machine_cost: Optional[Decimal] = None
    finish_cost: Optional[Decimal] = None
    packing_cost: Optional[Decimal] = None
    transport_cost: Optional[Decimal] = None
    other_cost: Optional[Decimal] = None
    overhead_percent: Optional[Decimal] = None
    margin_percent: Optional[Decimal] = None
    cost_price: Optional[Decimal] = None
    selling_price: Optional[Decimal] = None
    notes: Optional[str] = None
    # Set by the frontend when the user resolves a possible (fuzzy) match
    # as "Use Existing" - reuses that product instead of creating a new
    # one, same as matched_client_id in the Client importer.
    matched_product_id: Optional[int] = None
    skip: bool = False  # user chose not to import this row (e.g. unresolved possible match)

    @field_validator(
        "material_cost", "hardware_cost", "labour_cost", "machine_cost",
        "finish_cost", "packing_cost", "transport_cost", "other_cost",
        "cost_price", "selling_price",
    )
    @classmethod
    def cost_fields_not_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Cost/price fields cannot be negative")
        return v

    @field_validator("overhead_percent")
    @classmethod
    def overhead_percent_not_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Overhead percent cannot be negative")
        return v

    @field_validator("margin_percent")
    @classmethod
    def margin_percent_must_be_under_100(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v >= 100:
            raise ValueError("Margin percent must be less than 100% (100% margin implies an infinite selling price).")
        return v


class ProductImportCommitRequest(BaseModel):
    rows: List[ProductImportCommitRow]


class ProductImportCommitResult(BaseModel):
    created_products: int
    matched_existing: int = 0
    skipped: int
    product_ids: List[int]
    error: Optional[str] = None


# --- product_import.py ---
"""Excel import for the Product Master - same discipline as
app/modules/procurement/services.py (one fixed template shared by the download
and the parser, never writes a parsed row directly to the database,
preview/commit are two separate steps). Kept as a distinct module
rather than folded into the procurement module's purchase-import logic (app/modules/procurement/services.py) since products and purchases
are unrelated entities with an unrelated column set.
"""

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


REQUIRED_COLUMNS = ["Product Name *", "Unit *"]


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


def build_product_import_template() -> BytesIO:
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


def parse_product_uploaded_workbook(file_bytes: bytes) -> List[dict]:
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
    (see app.modules.clients.services.find_fuzzy_name_matches, reused here
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
        from app.modules.clients.services import find_fuzzy_name_matches
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


# --- rate_card_schemas.py ---
class RateCardImportRowPreview(BaseModel):
    row_number: int
    matched_rate_id: Optional[int] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    item_name: Optional[str] = None
    specification: Optional[str] = None
    location: Optional[str] = None
    uom: Optional[str] = None
    market_reference_rate: Optional[Decimal] = None
    woodful_cost_rate: Optional[Decimal] = None
    woodful_selling_rate: Optional[Decimal] = None
    overhead_percent: Optional[Decimal] = None
    target_margin_percent: Optional[Decimal] = None
    wastage_percent: Optional[Decimal] = None
    tax_percent: Optional[Decimal] = None
    source_type: Optional[str] = None
    source_reference: Optional[str] = None
    confidence: Optional[str] = None
    notes: Optional[str] = None
    is_update: bool = False
    errors: List[str] = []


class RateCardImportPreviewResponse(BaseModel):
    total_rows: int
    new_rows: int
    update_rows: int
    error_rows: int
    rows: List[RateCardImportRowPreview]


class RateCardImportCommitRow(BaseModel):
    matched_rate_id: Optional[int] = None
    category: str
    subcategory: Optional[str] = None
    item_name: str
    specification: Optional[str] = None
    location: str = "Indore, Madhya Pradesh"
    uom: str
    market_reference_rate: Optional[Decimal] = None
    woodful_cost_rate: Optional[Decimal] = None
    woodful_selling_rate: Optional[Decimal] = None
    overhead_percent: Optional[Decimal] = None
    target_margin_percent: Optional[Decimal] = None
    wastage_percent: Optional[Decimal] = None
    tax_percent: Optional[Decimal] = None
    source_type: str
    source_reference: Optional[str] = None
    confidence: str = "NOT_VERIFIED"
    notes: Optional[str] = None
    skip: bool = False

    # Reuses the exact same rules RateCardCreate enforces (see
    # app/schemas/rate_card.py) - the import commit path must not be
    # able to create a rate card the normal API would reject.
    @field_validator("uom")
    @classmethod
    def uom_must_be_standard(cls, v):
        return _validate_uom(v)

    @model_validator(mode="after")
    def uom_must_suit_category(self):
        if self.category and self.uom and not uom_allowed_for_category(self.category, self.uom):
            raise ValueError(f"'{self.uom}' is not an appropriate unit for category '{self.category}'.")
        return self

    @field_validator("source_type")
    @classmethod
    def source_type_must_be_known(cls, v):
        return _validate_source_type(v)

    @field_validator("confidence")
    @classmethod
    def confidence_must_be_known(cls, v):
        return _validate_confidence(v)

    @field_validator("target_margin_percent")
    @classmethod
    def margin_must_be_under_100(cls, v):
        return _validate_margin_under_100(v)

    @field_validator("market_reference_rate", "woodful_cost_rate", "woodful_selling_rate",
                      "overhead_percent", "wastage_percent", "tax_percent")
    @classmethod
    def rate_fields_not_negative(cls, v):
        return _validate_rate_field_not_negative(v)


class RateCardImportCommitRequest(BaseModel):
    rows: List[RateCardImportCommitRow]


class RateCardImportCommitResult(BaseModel):
    created: int
    updated: int
    skipped: int
    rate_ids: List[int]
    error: Optional[str] = None


# --- rate_card_import.py ---
"""Excel import for the Rate Master. Same discipline as
product_import.py (this same file)/the client-import logic in app/modules/clients/services.py: one fixed template shared by the
download and the parser, never writes a parsed row directly to the
database, preview/commit are two separate steps.

Business rule specific to this import: uploaded rates are NEVER
allowed to blindly overwrite a historical rate. Every committed row
goes through the exact same create-new-version path as a UI edit (see
rate_cards.py's revise_rate_card) - a Rate ID in the sheet identifies
WHICH item to version, it never lets the sheet dictate the new row's
own ID.
"""

RATE_IMPORT_COLUMNS = [
    "Rate ID", "Category", "Subcategory", "Item Name", "Specification", "Location", "UOM",
    "Market Reference Rate", "Woodful Cost Rate", "Woodful Selling Rate",
    "Overhead %", "Target Margin %", "Wastage %", "Tax %",
    "Source Type", "Source Reference", "Confidence", "Notes",
]


HEADER_ALIASES = {
    "rate id": "Rate ID", "item name": "Item Name", "item": "Item Name", "product/service": "Item Name",
    "category": "Category", "subcategory": "Subcategory", "specification": "Specification",
    "spec": "Specification", "location": "Location", "uom": "UOM", "unit": "UOM",
    "market reference rate": "Market Reference Rate", "market rate": "Market Reference Rate",
    "woodful cost rate": "Woodful Cost Rate", "cost rate": "Woodful Cost Rate",
    "woodful selling rate": "Woodful Selling Rate", "selling rate": "Woodful Selling Rate",
    "overhead %": "Overhead %", "overhead": "Overhead %",
    "target margin %": "Target Margin %", "margin": "Target Margin %", "margin %": "Target Margin %",
    "wastage %": "Wastage %", "wastage": "Wastage %",
    "tax %": "Tax %", "tax": "Tax %", "gst": "Tax %", "gst %": "Tax %",
    "source type": "Source Type", "source reference": "Source Reference", "source": "Source Reference",
    "confidence": "Confidence", "notes": "Notes",
}


for _col in RATE_IMPORT_COLUMNS:
    HEADER_ALIASES.setdefault(_col.lower(), _col)


REQUIRED_COLUMNS = ["Category", "Item Name", "UOM", "Source Type"]


EXAMPLE_ROWS = [
    {
        "Rate ID": "", "Category": "Material", "Subcategory": "Plywood", "Item Name": "Plywood - MR Grade",
        "Specification": "18mm, commercial/MR", "Location": "Indore, Madhya Pradesh", "UOM": "Sq Ft",
        "Market Reference Rate": 60, "Woodful Cost Rate": "", "Woodful Selling Rate": "",
        "Overhead %": 12, "Target Margin %": 30, "Wastage %": 5, "Tax %": 18,
        "Source Type": "INDORE_SUPPLIER", "Source Reference": "Indore plywood dealer listings, Aug 2026",
        "Confidence": "MEDIUM", "Notes": "New rate - leave Rate ID blank",
    },
    {
        "Rate ID": "RATE-001", "Category": "Material", "Subcategory": "Plywood", "Item Name": "Plywood - BWP Grade",
        "Specification": "18mm, waterproof/marine", "Location": "Indore, Madhya Pradesh", "UOM": "Sq Ft",
        "Market Reference Rate": 90, "Woodful Cost Rate": "", "Woodful Selling Rate": "",
        "Overhead %": 12, "Target Margin %": 30, "Wastage %": 5, "Tax %": 18,
        "Source Type": "INDORE_SUPPLIER", "Source Reference": "Indore waterproof plywood listings, Aug 2026",
        "Confidence": "MEDIUM", "Notes": "Existing rate - update by Rate ID, creates a new version",
    },
]


def build_rate_card_import_template() -> BytesIO:
    wb = Workbook()
    wb.remove(wb.active)
    write_sheet(
        wb, sheet_name="Rate Import", title="Woodful Creations - Rate Master Import Template",
        subtitle="Leave Rate ID blank to create a new rate. Enter an existing Rate ID to update it - this "
                  "creates a NEW version and never overwrites the old one, which stays available for "
                  "historical Estimates/Orders. Category, Item Name, UOM, and Source Type are required. "
                  f"Source Type must be one of: {', '.join(sorted(RATE_SOURCE_TYPES))}. "
                  f"Confidence must be one of: {', '.join(sorted(RATE_CONFIDENCE_LEVELS))}.",
        columns=RATE_IMPORT_COLUMNS, rows=EXAMPLE_ROWS,
    )
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


_MARKET_RANGE_HEADERS = ["Type", "Category", "Item/Grade", "Thickness/Basis", "UOM",
                          "Market_Low_INR", "Market_High_INR", "Source_Basis", "Notes"]


def _is_market_range_layout(values) -> bool:
    normalized = [str(v).strip() if v is not None else None for v in values]
    return all(h in normalized for h in _MARKET_RANGE_HEADERS)


def _infer_source_type(source_basis: Optional[str]) -> str:
    text = (source_basis or "").lower()
    if "indore" in text:
        return "INDORE_MARKET_LISTING"
    if "national" in text or "india" in text:
        return "NATIONAL_MARKET_BENCHMARK"
    return "NATIONAL_MARKET_BENCHMARK"


def parse_market_range_workbook(file_bytes: bytes) -> List[dict]:
    """Parses the Type/Category/Item-Grade/Thickness-Basis/UOM/
    Market_Low_INR/Market_High_INR/Source_Basis/Notes layout, mapping
    it to this module's canonical row shape:
        Category    <- Type            (top-level: Material/Furniture/...)
        Subcategory <- Category        (e.g. Plywood, Tables, CNC Cutting)
        Item Name   <- Item/Grade      (e.g. MR Commercial, Coffee Table)
        Specification <- Thickness/Basis
        Market Reference Rate <- midpoint of (Market_Low_INR, Market_High_INR)
        Source Type <- inferred from Source_Basis text (INDORE_* if
                        "Indore" appears, else NATIONAL_MARKET_BENCHMARK)
        Confidence  <- "LOW" (every row in this layout is an unverified
                        market reference BAND, never a fixed Woodful
                        rate - the source sheet's own Notes column says
                        so explicitly, e.g. "Do not use as fixed
                        Woodful rate", "Woodful must verify internal cost")
        Source Reference <- original Source_Basis, with the full
                        Low-High range appended so it's never lost by
                        collapsing to a midpoint.
    This mapping follows the spec's own Category -> Subcategory ->
    Product/Service -> Variant/Specification hierarchy exactly.
    """
    wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True)
    enforce_workbook_row_limit(wb)
    ws = wb.worksheets[0]

    header_row_idx = None
    for row in ws.iter_rows(min_row=1, max_row=5):
        values = [c.value for c in row]
        if _is_market_range_layout(values):
            header_row_idx = row[0].row
            break
    if header_row_idx is None:
        return []  # not this layout - caller falls back to the primary template parser

    rows = []
    for row in ws.iter_rows(min_row=header_row_idx + 1):
        values = [_clean(c.value) for c in row]
        if all(v is None for v in values):
            continue
        type_, category, item_grade, spec, uom, low, high, source_basis, notes = (values + [None] * 9)[:9]
        if not (type_ and item_grade and uom):
            continue  # skip malformed/incomplete rows rather than erroring the whole import

        low_n = normalize_number(low)
        high_n = normalize_number(high)
        midpoint = None
        if low_n is not None and high_n is not None:
            midpoint = ((low_n + high_n) / 2).quantize(Decimal("0.01"))
        elif low_n is not None:
            midpoint = low_n
        elif high_n is not None:
            midpoint = high_n

        range_text = f"₹{low}-₹{high}" if (low is not None and high is not None) else ""
        source_reference = " | ".join(filter(None, [source_basis, f"Market range {range_text}" if range_text else None]))

        rows.append({
            "Category": type_, "Subcategory": category, "Item Name": item_grade,
            "Specification": spec, "UOM": uom,
            "Market Reference Rate": midpoint,
            "Source Type": _infer_source_type(source_basis),
            "Source Reference": source_reference or None,
            "Confidence": "LOW",
            "Notes": notes,
        })
    return rows


def parse_rate_card_uploaded_workbook(file_bytes: bytes) -> List[dict]:
    # Real-world supplier/market-research files (e.g. the initial
    # Woodful Rate Master dataset) use a different, valid column
    # layout - detect and map it before falling back to the primary
    # template's own header set.
    market_range_rows = parse_market_range_workbook(file_bytes)
    if market_range_rows:
        return market_range_rows

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
            "Please use the downloaded template, or make sure Category, Item Name, UOM, and Source Type "
            "have a recognizable header and aren't duplicated."
        )

    rows = []
    for row in ws.iter_rows(min_row=header_row_idx + 1):
        values = [c.value for c in row]
        if all(_clean(v) is None for v in values):
            continue
        rows.append({name: _clean(values[idx]) if idx < len(values) else None for name, idx in col_index.items()})
    return rows


def validate_row(row: dict, existing_by_code: dict):
    """Validates one parsed row. Returns (result_dict, errors_list,
    is_update); never writes anything. rate_id present but unknown is
    an error (never silently treated as new)."""
    errors = []
    rate_code = row.get("Rate ID")
    matched = None
    if rate_code:
        matched = existing_by_code.get(rate_code.strip().upper())
        if not matched:
            errors.append(f"Rate ID not found: {rate_code!r}. Leave Rate ID blank to create a new rate.")

    for col in REQUIRED_COLUMNS:
        if not row.get(col):
            errors.append(f"{col} is required")

    uom = row.get("UOM")
    category = row.get("Category")
    if uom and uom not in STANDARD_UOMS:
        errors.append(f"'{uom}' is not a standard UOM")
    elif uom and category and not uom_allowed_for_category(category, uom):
        errors.append(f"'{uom}' is not an appropriate unit for category '{category}'")

    source_type_raw = row.get("Source Type")
    source_type = None
    if source_type_raw:
        normalized = source_type_raw.upper().replace(" ", "_")
        if normalized not in RATE_SOURCE_TYPES:
            errors.append(f"'{source_type_raw}' is not a recognized Source Type")
        else:
            source_type = normalized

    confidence_raw = row.get("Confidence")
    confidence = "NOT_VERIFIED"
    if confidence_raw:
        if confidence_raw.upper() not in RATE_CONFIDENCE_LEVELS:
            errors.append(f"'{confidence_raw}' is not a recognized Confidence level")
        else:
            confidence = confidence_raw.upper()

    numeric_fields = {}
    for col in ("Market Reference Rate", "Woodful Cost Rate", "Woodful Selling Rate",
                "Overhead %", "Target Margin %", "Wastage %", "Tax %"):
        raw = row.get(col)
        if raw is None:
            numeric_fields[col] = None
            continue
        val = normalize_number(raw)
        if val is None:
            errors.append(f"Invalid {col}: {raw!r}")
        numeric_fields[col] = val

    result = {
        "matched_rate_id": matched.id if matched else None,
        "category": row.get("Category"), "subcategory": row.get("Subcategory"),
        "item_name": row.get("Item Name"), "specification": row.get("Specification"),
        "location": row.get("Location") or "Indore, Madhya Pradesh", "uom": uom,
        "market_reference_rate": numeric_fields["Market Reference Rate"],
        "woodful_cost_rate": numeric_fields["Woodful Cost Rate"],
        "woodful_selling_rate": numeric_fields["Woodful Selling Rate"],
        "overhead_percent": numeric_fields["Overhead %"], "target_margin_percent": numeric_fields["Target Margin %"],
        "wastage_percent": numeric_fields["Wastage %"], "tax_percent": numeric_fields["Tax %"],
        "source_type": source_type, "source_reference": row.get("Source Reference"),
        "confidence": confidence, "notes": row.get("Notes"),
    }
    return result, errors, matched is not None
