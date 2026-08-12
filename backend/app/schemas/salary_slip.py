from pydantic import BaseModel, field_validator
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

    @field_validator("basic", "da", "hra", "overtime_amount", "pf_deduction", "tds_deduction",
                      "other_deductions", mode="before")
    @classmethod
    def blank_string_means_zero(cls, v):
        # An absent key already falls back to the Decimal("0") default
        # above - this handles the other real case, where the key IS
        # present but empty (e.g. a number input the user clicked into
        # and left blank), which Pydantic would otherwise reject as an
        # invalid Decimal rather than silently use the default.
        if v == "" or v is None:
            return "0"
        return v


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
