from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import datetime


class SalarySlipBase(BaseModel):
    employee_id: int
    month: str
    year: str
    basic: Decimal = Decimal("0")
    da: Decimal = Decimal("0")
    hra: Decimal = Decimal("0")
    overtime_amount: Decimal = Decimal("0")
    pf_deduction: Decimal = Decimal("0")
    tds_deduction: Decimal = Decimal("0")
    other_deductions: Decimal = Decimal("0")


class SalarySlipCreate(SalarySlipBase):
    pass


class SalarySlipUpdate(BaseModel):
    status: Optional[str] = None
    pf_deduction: Optional[Decimal] = None
    tds_deduction: Optional[Decimal] = None
    other_deductions: Optional[Decimal] = None


class SalarySlipResponse(SalarySlipBase):
    id: int
    net_salary: Decimal
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
