from pydantic import BaseModel, field_validator
from typing import Optional, List
from decimal import Decimal
from datetime import datetime

ATTRIBUTE_DATA_TYPES = ["text", "number", "select"]


class MaterialCategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None


class MaterialCategoryResponse(BaseModel):
    id: int
    business_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MaterialAttributeDefinitionCreate(BaseModel):
    name: str
    data_type: str = "text"
    unit_label: Optional[str] = None
    select_options: Optional[str] = None  # comma-separated, only meaningful when data_type="select"
    is_required: bool = False
    sort_order: int = 0

    @field_validator("data_type")
    @classmethod
    def validate_data_type(cls, v):
        if v not in ATTRIBUTE_DATA_TYPES:
            raise ValueError(f"data_type must be one of: {', '.join(ATTRIBUTE_DATA_TYPES)}")
        return v


class MaterialAttributeDefinitionResponse(BaseModel):
    id: int
    subcategory_id: int
    name: str
    data_type: str
    unit_label: Optional[str] = None
    select_options: Optional[str] = None
    is_required: bool
    sort_order: int

    class Config:
        from_attributes = True


class MaterialSubcategoryCreate(BaseModel):
    category_id: int
    name: str
    description: Optional[str] = None


class MaterialSubcategoryResponse(BaseModel):
    id: int
    business_id: Optional[str] = None
    category_id: int
    name: str
    description: Optional[str] = None
    attribute_definitions: List[MaterialAttributeDefinitionResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MaterialCategoryWithSubcategories(MaterialCategoryResponse):
    subcategories: List[MaterialSubcategoryResponse] = []


class MaterialAttributeValueInput(BaseModel):
    """What the frontend sends when setting a material's attribute
    values - keyed by attribute_definition_id since the frontend already
    has the subcategory's attribute definitions loaded to render the
    right form fields."""
    attribute_definition_id: int
    value_text: Optional[str] = None
    value_number: Optional[Decimal] = None


class MaterialAttributeValueResponse(BaseModel):
    id: int
    attribute_definition_id: int
    attribute_name: str
    value_text: Optional[str] = None
    value_number: Optional[Decimal] = None
    display_value: str

    class Config:
        from_attributes = True
