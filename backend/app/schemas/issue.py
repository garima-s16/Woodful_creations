from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class MaterialIssueBase(BaseModel):
    issue_id: str
    project_id: int
    material_id: int
    quantity_issued: int
    unit: str

class MaterialIssueCreate(MaterialIssueBase):
    issued_to: Optional[str] = None
    department: Optional[str] = None
    purpose: Optional[str] = None
    approved_by: Optional[str] = None
    remarks: Optional[str] = None

class MaterialIssueUpdate(BaseModel):
    quantity_issued: Optional[int] = None
    issued_to: Optional[str] = None
    department: Optional[str] = None
    purpose: Optional[str] = None
    approved_by: Optional[str] = None
    remarks: Optional[str] = None

class MaterialIssueResponse(MaterialIssueBase):
    id: int
    date: datetime
    issued_to: Optional[str]
    department: Optional[str]
    purpose: Optional[str]
    approved_by: Optional[str]
    remarks: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
