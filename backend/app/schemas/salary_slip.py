from pydantic import BaseModel, field_validator, model_validator
from typing import Optional
from decimal import Decimal
from datetime import datetime


class SalarySlipBase(BaseModel):
    employee_id: int
    month: str
    year: str
    working_days: Decimal = Decimal("26")
    paid_days: Decimal = Decimal("26")
    basic: Decimal = Decimal("0")
    da: Decimal = Decimal("0")
    hra: Decimal = Decimal("0")
    overtime_amount: Decimal = Decimal("0")
    pf_deduction: Decimal = Decimal("0")
    tds_deduction: Decimal = Decimal("0")
    other_deductions: Decimal = Decimal("0")

    @field_validator("working_days", "paid_days")
    @classmethod
    def _must_be_positive(cls, v, info):
        if v <= 0:
            raise ValueError(f"{info.field_name} must be greater than 0")
        return v

    @model_validator(mode="after")
    def _paid_days_within_working_days(self):
        if self.paid_days > self.working_days:
            raise ValueError("paid_days cannot exceed working_days")
        return self


class SalarySlipCreate(SalarySlipBase):
    pass


class SalarySlipUpdate(BaseModel):
    status: Optional[str] = None
    working_days: Optional[Decimal] = None
    paid_days: Optional[Decimal] = None
    pf_deduction: Optional[Decimal] = None
    tds_deduction: Optional[Decimal] = None
    other_deductions: Optional[Decimal] = None

    @field_validator("working_days", "paid_days")
    @classmethod
    def _must_be_positive(cls, v, info):
        if v is not None and v <= 0:
            raise ValueError(f"{info.field_name} must be greater than 0")
        return v


class SalarySlipResponse(SalarySlipBase):
    id: int
    business_id: str
    net_salary: Decimal
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
