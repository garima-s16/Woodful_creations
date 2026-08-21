from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from decimal import Decimal
from datetime import datetime

from app.utils.validators import validate_phone


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
    address: Optional[str] = None
    remarks: Optional[str] = None
    pan: Optional[str] = None
    uan: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    tax_regime: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def phone_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        # Phone stays optional for an employee (unlike Client Master,
        # where it's mandatory) - but IF one is given, it must be
        # exactly 10 digits, same rule and same exact message as
        # Client Master. emergency_contact is left freeform (it may
        # legitimately include a name/relation, not just a bare number).
        if v is None or v == "":
            return v
        v = v.strip()
        if not validate_phone(v):
            raise ValueError("Please enter valid mobile number")
        return v


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
    address: Optional[str] = None
    remarks: Optional[str] = None
    pan: Optional[str] = None
    uan: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    tax_regime: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def phone_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return v
        v = v.strip()
        if not validate_phone(v):
            raise ValueError("Please enter valid mobile number")
        return v


class EmployeeResponse(EmployeeBase):
    id: int
    business_id: Optional[str] = None
    monthly_salary: Optional[Decimal] = None
    daily_wage: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
