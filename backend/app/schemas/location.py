from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class LocationCreate(BaseModel):
    name: str
    location_type: Optional[str] = None
    parent_id: Optional[int] = None


class LocationResponse(BaseModel):
    id: int
    business_id: Optional[str] = None
    name: str
    location_type: Optional[str] = None
    parent_id: Optional[int] = None
    full_path: str

    class Config:
        from_attributes = True


class LocationTreeResponse(LocationResponse):
    children: List["LocationTreeResponse"] = []


LocationTreeResponse.model_rebuild()
