from pydantic import BaseModel, field_validator
from typing import Optional, List
from decimal import Decimal


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
