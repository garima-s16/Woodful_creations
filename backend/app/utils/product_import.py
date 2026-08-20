"""Product Master bulk import (Family 21), built entirely on the
reusable utils/bulk_import.py infrastructure. Same discipline as
Purchase Import (Family 6): the template download and the parser share
one fixed column list, nothing is ever written to the database until
an explicit, user-reviewed /commit call, and a Product's IDs
(product_code, business_id) are always server-generated - a row's
"Product Name"/"SKU" are the only identifying input a person ever
types."""
from decimal import Decimal
from typing import Optional

from app.models.product import PRODUCT_TYPES
from app.models.product_category import ProductCategory, ProductSubcategory
from app.utils.bulk_import import (
    build_header_aliases, build_import_template as _build_template,
    normalize_number, normalize_match_key, clean_cell,
)

PRODUCT_IMPORT_COLUMNS = [
    "Product Name", "SKU", "Type", "Category", "Subcategory", "Description",
    "Length", "Width", "Height", "Dimension Unit", "Finish", "Unit",
    "Cost Price", "Selling Price", "Tax %", "Lead Time Days", "Notes",
]

HEADER_ALIASES = build_header_aliases(PRODUCT_IMPORT_COLUMNS, extra_aliases={
    "name": "Product Name", "product": "Product Name",
    "sku code": "SKU", "product type": "Type", "product_type": "Type",
    "sub category": "Subcategory", "sub-category": "Subcategory",
    "dim unit": "Dimension Unit", "uom": "Unit",
    "cost": "Cost Price", "price": "Selling Price", "sale price": "Selling Price",
    "gst": "Tax %", "gst%": "Tax %", "tax": "Tax %",
    "lead time": "Lead Time Days", "lead time (days)": "Lead Time Days",
})

EXAMPLE_ROWS = [
    {
        "Product Name": "Sliding Wardrobe - 3 Door", "SKU": "WD-SLD-3D", "Type": "standard",
        "Category": "Bedroom Furniture", "Subcategory": "Wardrobes",
        "Description": "3-door sliding wardrobe with laminate finish",
        "Length": 96, "Width": 24, "Height": 84, "Dimension Unit": "in",
        "Finish": "White Laminate", "Unit": "Piece",
        "Cost Price": 42000, "Selling Price": 58000, "Tax %": 18, "Lead Time Days": 21, "Notes": "",
    },
    {
        "Product Name": "Custom Pooja Mandir - HDHMR", "SKU": "", "Type": "custom",
        "Category": "Mandir", "Subcategory": "Wall Mounted",
        "Description": "Client-specific temple unit, carved front panel",
        "Length": 36, "Width": 15, "Height": 48, "Dimension Unit": "in",
        "Finish": "Natural Wood", "Unit": "Piece",
        "Cost Price": 18000, "Selling Price": 27000, "Tax %": 18, "Lead Time Days": 14,
        "Notes": "Made to order for a specific client",
    },
]


def build_product_import_template():
    return _build_template(
        sheet_name="Product Import", title="Woodful Creations - Product Master Import Template",
        subtitle="Fill in one row per product. Category/Subcategory must already exist "
                  "(create them on the Product Master page first). Do not change the column headers.",
        columns=PRODUCT_IMPORT_COLUMNS, example_rows=EXAMPLE_ROWS,
    )


def validate_and_match_row(row: dict, db, categories_by_name=None, subcategories_by_name=None):
    """Validates one parsed row and matches Category/Subcategory against
    real records (case-insensitive exact match, never fuzzy). Returns
    (result_dict, errors_list). Never writes anything."""
    errors = []
    name = row.get("Product Name")
    if not name:
        errors.append("Product Name is required")

    product_type = (row.get("Type") or "standard").strip().lower() if row.get("Type") else "standard"
    if product_type not in PRODUCT_TYPES:
        errors.append(f'Type must be one of: {", ".join(PRODUCT_TYPES)} (got {row.get("Type")!r})')

    subcategory_id = None
    category_name = row.get("Category")
    subcategory_name = row.get("Subcategory")
    if subcategory_name:
        sub = (subcategories_by_name or {}).get(normalize_match_key(subcategory_name))
        if not sub:
            errors.append(
                f'No existing subcategory matches "{subcategory_name}"'
                + (f' under "{category_name}"' if category_name else "")
                + " - create it on the Product Master page first, then re-upload."
            )
        else:
            subcategory_id = sub.id

    def _num(field):
        if row.get(field) is None:
            return None
        val = normalize_number(row[field])
        if val is None:
            errors.append(f"Invalid {field}: {row[field]!r}")
        return val

    length = _num("Length")
    width = _num("Width")
    height = _num("Height")
    cost_price = _num("Cost Price") or Decimal("0")
    selling_price = _num("Selling Price") or Decimal("0")
    tax_percent = _num("Tax %")
    if tax_percent is None:
        tax_percent = Decimal("18")

    lead_time_days = None
    if row.get("Lead Time Days") is not None:
        lt = normalize_number(row["Lead Time Days"])
        if lt is None:
            errors.append(f'Invalid Lead Time Days: {row["Lead Time Days"]!r}')
        else:
            lead_time_days = int(lt)

    dimension_unit = (clean_cell(row.get("Dimension Unit")) or "in").lower()
    if dimension_unit not in ("in", "cm", "ft", "mm"):
        errors.append(f'Dimension Unit must be one of: in, cm, ft, mm (got {row.get("Dimension Unit")!r})')

    result = {
        "name": name, "sku": clean_cell(row.get("SKU")), "product_type": product_type,
        "category_name": category_name, "subcategory_name": subcategory_name, "subcategory_id": subcategory_id,
        "description": clean_cell(row.get("Description")),
        "length": length, "width": width, "height": height, "dimension_unit": dimension_unit,
        "finish": clean_cell(row.get("Finish")), "unit": clean_cell(row.get("Unit")) or "Piece",
        "cost_price": cost_price, "selling_price": selling_price, "tax_percent": tax_percent,
        "lead_time_days": lead_time_days, "notes": clean_cell(row.get("Notes")),
    }
    return result, errors
