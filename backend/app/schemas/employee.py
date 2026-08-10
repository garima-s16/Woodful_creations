from decimal import Decimal
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class EmployeeBase(BaseModel):
    name: str
    email: EmailStr
    phone: str
    position: str
    department: str
    salary: Decimal

class EmployeeCreate(EmployeeBase):
    pass

class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    salary: Optional[Decimal] = None
    is_active: Optional[bool] = None

class EmployeeResponse(EmployeeBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True