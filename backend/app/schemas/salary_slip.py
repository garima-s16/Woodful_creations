from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class SalarySlipBase(BaseModel):
    employee_id: int
    month: str
    year: str
    basic_salary: float
    allowances: float = 0.0
    deductions: float = 0.0

class SalarySlipCreate(SalarySlipBase):
    pass

class SalarySlipUpdate(BaseModel):
    basic_salary: Optional[float] = None
    allowances: Optional[float] = None
    deductions: Optional[float] = None
    status: Optional[str] = None

class SalarySlipResponse(SalarySlipBase):
    id: int
    net_salary: float
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True