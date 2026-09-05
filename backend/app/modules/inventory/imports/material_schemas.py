from pydantic import BaseModel, field_validator
from typing import Optional, List
from decimal import Decimal


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
