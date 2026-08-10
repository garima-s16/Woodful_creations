from decimal import Decimal
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class SalarySlipBase(BaseModel):
    employee_id: int
    month: str
    year: str
    basic_salary: Decimal
    allowances: Decimal = 0
    deductions: Decimal = 0

class SalarySlipCreate(SalarySlipBase):
    pass

class SalarySlipUpdate(BaseModel):
    basic_salary: Optional[Decimal] = None
    allowances: Optional[Decimal] = None
    deductions: Optional[Decimal] = None
    status: Optional[str] = None

class SalarySlipResponse(SalarySlipBase):
    id: int
    net_salary: Decimal
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True