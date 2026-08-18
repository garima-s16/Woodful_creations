from pydantic import BaseModel, EmailStr
from typing import Optional
from decimal import Decimal
from datetime import datetime


class EmployeeBase(BaseModel):
    employee_code: Optional[str] = None  # server-generated on create, ignored if supplied
    name: str
    designation: Optional[str] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    manager: Optional[str] = None
    joining_date: Optional[datetime] = None
    monthly_salary: Decimal = Decimal("0")
    status: str = "Active"
    emergency_contact: Optional[str] = None
    remarks: Optional[str] = None
    pan: Optional[str] = None
    uan: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    tax_regime: Optional[str] = None


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    manager: Optional[str] = None
    monthly_salary: Optional[Decimal] = None
    status: Optional[str] = None
    emergency_contact: Optional[str] = None
    remarks: Optional[str] = None
    pan: Optional[str] = None
    uan: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    tax_regime: Optional[str] = None


class EmployeeResponse(EmployeeBase):
    id: int
    business_id: Optional[str] = None
    monthly_salary: Optional[Decimal] = None
    daily_wage: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
