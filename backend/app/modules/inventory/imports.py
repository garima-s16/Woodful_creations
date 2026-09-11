"""Inventory import processing: material Excel import schemas,
parse/validate/commit logic, and the material-name interpreter
(intelligent field-defaults suggestion). Combines the former
material_schemas.py, material_import.py, and material_interpreter.py."""
from pydantic import BaseModel, field_validator
from typing import Optional, List
from decimal import Decimal
from io import BytesIO
from typing import List, Optional
from app.shared_imports import _clean, resolve_header_row_bare
import openpyxl
from openpyxl import Workbook
from app.shared import write_sheet, write_instructions_sheet
from app.shared_imports import normalize_match_key, normalize_number, enforce_workbook_row_limit
import re
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.modules.inventory.models import Material, MaterialSubcategory


# --- material_schemas.py ---
class MaterialImportRowPreview(BaseModel):
    row_number: int
    name: Optional[str] = None
    category: Optional[str] = None
    subcategory_id: Optional[int] = None
    brand_grade: Optional[str] = None
    thickness_size: Optional[str] = None
    unit: Optional[str] = None
    supplier_id: Optional[int] = None
    opening_stock: Optional[Decimal] = None
    minimum_stock: Optional[Decimal] = None
    location_id: Optional[int] = None
    is_active: bool = True
    matched_material_id: Optional[int] = None
    is_duplicate: bool = False
    possible_match_material_id: Optional[int] = None
    possible_match_name: Optional[str] = None
    errors: List[str] = []


class MaterialImportPreviewResponse(BaseModel):
    total_rows: int
    new_rows: int
    duplicate_rows: int
    error_rows: int
    rows: List[MaterialImportRowPreview]


class MaterialImportCommitRow(BaseModel):
    """Echoes one reviewed row back for actual creation. A row flagged
    as a duplicate on preview is only created if the caller explicitly
    confirms - never silently creating a second material with the same
    name, matching the Product/Client importers' established rule."""
    name: str
    category: Optional[str] = None
    subcategory_id: Optional[int] = None
    brand_grade: Optional[str] = None
    thickness_size: Optional[str] = None
    unit: str = "Nos"
    supplier_id: Optional[int] = None
    opening_stock: Decimal = Decimal("0")
    minimum_stock: Decimal = Decimal("0")
    location_id: Optional[int] = None
    is_active: bool = True
    # Set by the frontend when the user resolves a possible (fuzzy) match
    # as "Use Existing" - reuses that material instead of creating a new
    # one, same as matched_product_id in the Product importer.
    matched_material_id: Optional[int] = None
    skip: bool = False  # user chose not to import this row (e.g. unresolved possible match)

    @field_validator("opening_stock")
    @classmethod
    def opening_stock_not_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Opening stock cannot be negative")
        return v

    @field_validator("minimum_stock")
    @classmethod
    def minimum_stock_not_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Minimum stock cannot be negative")
        return v


class MaterialImportCommitRequest(BaseModel):
    rows: List[MaterialImportCommitRow]


class MaterialImportCommitResult(BaseModel):
    created_materials: int
    matched_existing: int = 0
    skipped: int
    material_ids: List[int]
    error: Optional[str] = None


# --- material_import.py ---
"""Excel import for the Material Master. Same
discipline as app/modules/catalog/imports.py: one fixed template shared by
the download and the parser, never writes a parsed row directly to the
database (preview/commit are two separate steps), and reuses the same
shared fuzzy-match logic as every other importer (see
app.modules.clients.services.find_fuzzy_name_matches) so a typo like
"Fevikol" vs an existing "Fevicol" is caught the same way here as it
would be in the Material UI's own duplicate check.

Stock fields are handled the same way materials.py's own create_material
route already does: only Opening Stock is ever accepted from a row -
current_stock/total_purchased/total_issued are maintained transactionally
by StockService from real Purchase/Issue records and are never
overwritten by an import (section 6).
"""

TEMPLATE_VERSION = "1.0"


MATERIAL_IMPORT_COLUMNS = [
    "Material Name *", "Category", "Subcategory", "Brand / Grade", "Thickness / Size",
    "Unit *", "Supplier", "Opening Stock", "Minimum Stock", "Location", "Active",
]


HEADER_ALIASES = {
    "material": "Material Name *",
    "material name": "Material Name *",
    "name": "Material Name *",
    "category": "Category",
    "material category": "Category",
    "subcategory": "Subcategory",
    "sub category": "Subcategory",
    "material subcategory": "Subcategory",
    "brand": "Brand / Grade",
    "brand / grade": "Brand / Grade",
    "brand/grade": "Brand / Grade",
    "grade": "Brand / Grade",
    "thickness": "Thickness / Size",
    "thickness / size": "Thickness / Size",
    "thickness/size": "Thickness / Size",
    "size": "Thickness / Size",
    "unit": "Unit *",
    "supplier": "Supplier",
    "opening stock": "Opening Stock",
    "minimum stock": "Minimum Stock",
    "min stock": "Minimum Stock",
    "reorder level": "Minimum Stock",
    "location": "Location",
    "active": "Active",
    "is active": "Active",
}


for _col in MATERIAL_IMPORT_COLUMNS:
    HEADER_ALIASES.setdefault(_col.lower(), _col)
    HEADER_ALIASES.setdefault(_col.rstrip(" *").lower(), _col)


REQUIRED_COLUMNS = ["Material Name *", "Unit *"]


TRUE_STRINGS = {"true", "yes", "y", "1", "active"}


FALSE_STRINGS = {"false", "no", "n", "0", "inactive"}


EXAMPLE_ROWS = [
    {
        "Material Name *": "Fevicol SH Adhesive", "Category": "", "Subcategory": "",
        "Brand / Grade": "Fevicol", "Thickness / Size": "1 kg can", "Unit *": "Nos", "Supplier": "",
        "Opening Stock": 10, "Minimum Stock": 5, "Location": "", "Active": "Yes",
    },
    {
        "Material Name *": "BWP Plywood 18mm", "Category": "", "Subcategory": "",
        "Brand / Grade": "Century Ply", "Thickness / Size": "18mm", "Unit *": "Sheet", "Supplier": "",
        "Opening Stock": 25, "Minimum Stock": 10, "Location": "", "Active": "Yes",
    },
]


MATERIAL_FIELD_DOCS = [
    {"name": "Material Name *", "mandatory": True, "meaning": "Full name of the material as it should appear in Material Master.",
     "format": "Free text."},
    {"name": "Category", "mandatory": False, "meaning": "Top-level material grouping.",
     "format": "Must match an existing Material Category name exactly, or leave blank."},
    {"name": "Subcategory", "mandatory": False, "meaning": "More specific grouping within the category.",
     "format": "Must match an existing Material Subcategory name exactly, or leave blank."},
    {"name": "Brand / Grade", "mandatory": False, "meaning": "Brand or quality grade.", "format": "Free text."},
    {"name": "Thickness / Size", "mandatory": False, "meaning": "Thickness or size specification, where applicable.", "format": "Free text."},
    {"name": "Unit *", "mandatory": True, "meaning": "The unit this material is stocked/measured in.", "format": "Free text, e.g. Sheet, Kg, Nos, Litre."},
    {"name": "Supplier", "mandatory": False, "meaning": "The material's primary supplier.",
     "format": "Must match an existing Supplier name exactly, or leave blank. Import the Supplier first if it doesn't exist yet."},
    {"name": "Opening Stock", "mandatory": False,
     "meaning": "Starting stock quantity at the time this material is added. Only used once, when the material is created.",
     "format": "Number."},
    {"name": "Minimum Stock", "mandatory": False, "meaning": "Reorder threshold - below this, the material shows as Low Stock.", "format": "Number."},
    {"name": "Location", "mandatory": False, "meaning": "Where this material is stored.",
     "format": "Must match an existing Location name exactly, or leave blank."},
    {"name": "Active", "mandatory": False, "meaning": "Whether this material is in active use.",
     "format": "Yes/No. Defaults to Yes if left blank."},
]


def build_import_template() -> BytesIO:
    wb = Workbook()
    wb.remove(wb.active)
    write_sheet(
        wb, sheet_name="Materials", title="Woodful Creations - Material Import Template",
        subtitle="Material Name and Unit are required for every row (marked with *). Material ID is generated "
                  "automatically - do not add a Material ID column. Current Stock is never set here - only "
                  "Opening Stock, used once when the material is created; ongoing stock is maintained through "
                  "Purchases/Issues. Do not change the column headers.",
        columns=MATERIAL_IMPORT_COLUMNS, rows=EXAMPLE_ROWS,
    )
    write_instructions_sheet(
        wb, template_name="Woodful Material Import Template", version=TEMPLATE_VERSION,
        field_docs=MATERIAL_FIELD_DOCS,
        id_rule="Material ID is system-generated and never typed in by hand. Leave any ID column out entirely - "
                "there is none in this template.",
        duplicate_rule="A row is only treated as an existing material if its name matches an existing material "
                        "exactly - it will be reused, not re-created. A row whose name closely resembles (but "
                        "doesn't exactly match) an existing material - e.g. \"Fevikol\" vs an existing \"Fevicol\" "
                        "- is flagged as a possible match during preview; you will be asked to confirm whether to "
                        "use the existing material or create a new one. Nothing is merged or created automatically "
                        "on a possible match.",
        extra_notes=[
            "A completely blank row is skipped. A row with only some fields filled in is still validated - "
            "if Material Name or Unit is missing, that row will show an error.",
            "Current Stock, Total Purchased, and Total Issued are never set through this import - they are "
            "maintained automatically from real Purchase and Issue transactions. Only Opening Stock is used, "
            "and only when the material is first created.",
            "Category, Subcategory, Supplier, and Location must match an existing name exactly if provided - "
            "this import does not create new categories, suppliers, or locations on your behalf. The sample "
            "rows leave these blank since category/subcategory names are set up per business - check Material "
            "Master for the exact names already in use before filling these columns in.",
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
            "Please use the downloaded template, or make sure Material Name and Unit "
            "have a recognizable header and aren't duplicated."
        )

    rows = []
    for row in ws.iter_rows(min_row=header_row_idx + 1):
        values = [c.value for c in row]
        if all(_clean(v) is None for v in values):
            continue
        rows.append({name: _clean(values[idx]) if idx < len(values) else None for name, idx in col_index.items()})
    return rows


def validate_and_match_row(row: dict, existing_by_name: dict, categories_by_name: dict,
                            subcategories_by_name: dict, suppliers_by_name: dict, locations_by_name: dict,
                            fuzzy_candidates: Optional[list] = None):
    """Validates one parsed row, resolves Category/Subcategory/Supplier/
    Location by exact (case-insensitive) name against what already
    exists - never creating new master data on the material's behalf -
    and checks for an existing/possible-match material by name using the
    same shared fuzzy logic every other importer uses. Never
    writes anything."""
    errors = []
    name = row.get("Material Name *")
    if not name:
        errors.append("Material Name is required")

    unit = row.get("Unit *")
    if not unit:
        errors.append("Unit is required")

    category_name = row.get("Category")
    subcategory_id = None
    resolved_category_name = category_name
    subcat_text = row.get("Subcategory")
    if subcat_text:
        subcat = subcategories_by_name.get(normalize_match_key(subcat_text))
        if not subcat:
            errors.append(f"Subcategory not found: {subcat_text!r} - create it in Material Master first, or leave blank")
        else:
            subcategory_id = subcat.id
            resolved_category_name = subcat.category.name
    elif category_name and normalize_match_key(category_name) not in categories_by_name:
        errors.append(f"Category not found: {category_name!r} - create it in Material Master first, or leave blank")

    supplier_id = None
    supplier_text = row.get("Supplier")
    if supplier_text:
        supplier = suppliers_by_name.get(normalize_match_key(supplier_text))
        if not supplier:
            errors.append(f"Supplier not found: {supplier_text!r} - import/create the supplier first, or leave blank")
        else:
            supplier_id = supplier.id

    location_id = None
    location_text = row.get("Location")
    if location_text:
        location = locations_by_name.get(normalize_match_key(location_text))
        if not location:
            errors.append(f"Location not found: {location_text!r} - create it in Locations first, or leave blank")
        else:
            location_id = location.id

    opening_stock, e1 = None, None
    raw_opening = row.get("Opening Stock")
    if raw_opening is not None:
        opening_stock = normalize_number(raw_opening)
        if opening_stock is None:
            e1 = f"Invalid Opening Stock: {raw_opening!r}"
    minimum_stock, e2 = None, None
    raw_min = row.get("Minimum Stock")
    if raw_min is not None:
        minimum_stock = normalize_number(raw_min)
        if minimum_stock is None:
            e2 = f"Invalid Minimum Stock: {raw_min!r}"
    for e in (e1, e2):
        if e:
            errors.append(e)

    raw_active = row.get("Active")
    is_active = True
    if raw_active is not None:
        key = str(raw_active).strip().lower()
        if key in TRUE_STRINGS:
            is_active = True
        elif key in FALSE_STRINGS:
            is_active = False
        else:
            errors.append(f"Active must be Yes/No (got {raw_active!r})")

    matched = existing_by_name.get(normalize_match_key(name)) if name else None

    possible_match = None
    if not matched and name and fuzzy_candidates is not None:
        from app.modules.clients.services import find_fuzzy_name_matches
        fuzzy_hits = find_fuzzy_name_matches(db=None, name=name, candidates=fuzzy_candidates, limit=1)
        possible_match = fuzzy_hits[0] if fuzzy_hits else None

    result = {
        "name": name, "category": resolved_category_name, "subcategory_id": subcategory_id,
        "brand_grade": row.get("Brand / Grade"), "thickness_size": row.get("Thickness / Size"), "unit": unit,
        "supplier_id": supplier_id, "opening_stock": opening_stock or Decimal("0"),
        "minimum_stock": minimum_stock or Decimal("0"), "location_id": location_id, "is_active": is_active,
        "matched_material_id": matched.id if matched else None,
        "is_duplicate": matched is not None,
        "possible_match_material_id": possible_match.id if possible_match else None,
        "possible_match_name": possible_match.name if possible_match else None,
    }
    return result, errors


# --- material_interpreter.py ---
"""Interprets a free-typed material name (e.g. "HDHMR 6mm") into a
thickness/specification and a suggested Category/Subcategory - the
shared logic behind both the chatbot's existing material-creation
proposal (chat_inventory._route_material_action) and the material
creation form's "intelligent defaults".

Category/Subcategory names are entirely user-defined (Category ->
Subcategory -> Material, never hard-coded per the product's own
principle - see MaterialCategory/MaterialSubcategory docstrings), so
this can never hard-code "HDHMR means Board & Wood Materials". Instead
it matches the typed name against subcategories and materials the
business has ALREADY created - the same "search across name and
thickness_size" approach the chatbot already uses elsewhere
(_route_material_action, _route_ambiguous_hindi_add) - and only
returns a suggestion when it's actually confident, never a guess
dressed up as a fact.
"""

THICKNESS_RE = re.compile(r"(\d+(?:\.\d+)?\s*mm)", re.IGNORECASE)


_STOPWORDS = {"the", "a", "an", "of", "for", "sheet", "sheets", "board", "boards"}


def extract_thickness(name: str) -> Optional[str]:
    """"HDHMR 6mm" -> "6mm". None if no thickness-like token is present -
    never invented from an unrelated number."""
    match = THICKNESS_RE.search(name or "")
    return match.group(1).replace(" ", "") if match else None


def _base_tokens(name: str) -> list:
    """The name with any thickness token and units/stopwords stripped,
    e.g. "HDHMR 6mm Sheet" -> ["hdhmr"] - what's left is the part that
    actually identifies the material type, used to match against
    existing subcategories/materials."""
    without_thickness = THICKNESS_RE.sub("", name or "")
    words = re.findall(r"[A-Za-z]+", without_thickness.lower())
    return [w for w in words if len(w) > 2 and w not in _STOPWORDS]


def interpret_material_name(db: Session, name: str) -> dict:
    """Returns a suggestion dict:
        {
          "thickness_size": "6mm" | None,
          "category_id": int | None, "category_name": str | None,
          "subcategory_id": int | None, "subcategory_name": str | None,
          "confidence": "high" | "medium" | "none",
          "matched_on": str,  # human-readable explanation, for transparency
        }
    Never raises, never invents a category that doesn't already exist.
    The caller (route/chatbot) decides whether "none" confidence means
    showing no suggestion at all - this function's job is only to say
    how sure it is, not to force a value into the form.
    """
    thickness = extract_thickness(name)
    tokens = _base_tokens(name)

    result = {
        "thickness_size": thickness,
        "category_id": None, "category_name": None,
        "subcategory_id": None, "subcategory_name": None,
        "confidence": "none", "matched_on": "",
    }
    if not tokens:
        return result

    # 1) HIGH confidence: an existing Subcategory's own name appears in
    # (or contains) what was typed - e.g. typing "HDHMR 6mm" when a
    # "HDHMR" subcategory already exists under some category.
    subcategories = db.query(MaterialSubcategory).all()
    best_subcategory = None
    best_len = 0
    lowered_name = (name or "").lower()
    for sub in subcategories:
        sub_lower = sub.name.lower()
        if sub_lower in lowered_name or any(sub_lower == t for t in tokens):
            if len(sub_lower) > best_len:
                best_subcategory = sub
                best_len = len(sub_lower)
    if best_subcategory:
        result.update({
            "category_id": best_subcategory.category_id,
            "category_name": best_subcategory.category.name if best_subcategory.category else None,
            "subcategory_id": best_subcategory.id, "subcategory_name": best_subcategory.name,
            "confidence": "high",
            "matched_on": f"matches existing subcategory \"{best_subcategory.name}\"",
        })
        return result

    # 2) MEDIUM confidence: an existing Material whose own name shares a
    # significant word already has a subcategory/category assigned -
    # e.g. "HDHMR 6mm" typed when "HDHMR 18mm" already exists and is
    # filed under Board & Wood Materials > HDHMR. Same word-matching
    # approach _route_material_action already uses for material search.
    query = db.query(Material).filter(Material.subcategory_id.isnot(None))
    query = query.filter(or_(*[Material.name.ilike(f"%{t}%") for t in tokens]))
    existing = query.first()
    if existing and existing.subcategory:
        result.update({
            "category_id": existing.subcategory.category_id,
            "category_name": existing.subcategory.category.name if existing.subcategory.category else None,
            "subcategory_id": existing.subcategory_id, "subcategory_name": existing.subcategory.name,
            "confidence": "medium",
            "matched_on": f"similar to existing material \"{existing.name}\"",
        })
        return result

    # Nothing to go on - explicitly "none", so the caller shows no
    # suggestion rather than a fabricated one.
    return result
