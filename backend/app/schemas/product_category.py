from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ProductCategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProductCategoryResponse(BaseModel):
    id: int
    business_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductSubcategoryCreate(BaseModel):
    category_id: int
    name: str
    description: Optional[str] = None


class ProductSubcategoryResponse(BaseModel):
    id: int
    business_id: Optional[str] = None
    category_id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductCategoryWithSubcategories(ProductCategoryResponse):
    subcategories: List[ProductSubcategoryResponse] = []
