"""Lookup / dropdown-list tables, one per settings list across the three
source workbooks (Stock, Staff & Tasks, Order & Sales). Kept as simple
name/description rows, editable by master users, matching the "Settings"
sheet pattern in each workbook."""
from sqlalchemy import Column, String
from app.platform.database.base import BaseModel


class _LookupMixin:
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(255), nullable=True)


# --- Stock Management > Settings ---
class Unit(_LookupMixin, BaseModel):
    __tablename__ = "units"


class StockStatus(_LookupMixin, BaseModel):
    __tablename__ = "stock_statuses"


class StockPaymentStatus(_LookupMixin, BaseModel):
    __tablename__ = "stock_payment_statuses"


class SupplierTerm(_LookupMixin, BaseModel):
    __tablename__ = "supplier_terms"


# --- Staff & Tasks Management > Settings ---
class Department(_LookupMixin, BaseModel):
    __tablename__ = "departments"


class TaskStatus(_LookupMixin, BaseModel):
    __tablename__ = "task_statuses"


class AttendanceStatus(_LookupMixin, BaseModel):
    __tablename__ = "attendance_statuses"


class Machine(_LookupMixin, BaseModel):
    __tablename__ = "machines"


# --- Order & Sales Management > Settings ---
class ProjectStatus(_LookupMixin, BaseModel):
    __tablename__ = "project_statuses"


class Priority(_LookupMixin, BaseModel):
    """Shared Low/Medium/High/Urgent list - identical values are used by
    both Orders and Daily Tasks in the source workbooks."""
    __tablename__ = "priorities"


class PaymentMode(_LookupMixin, BaseModel):
    __tablename__ = "payment_modes"


class LeadSource(_LookupMixin, BaseModel):
    __tablename__ = "lead_sources"


class ProjectType(_LookupMixin, BaseModel):
    __tablename__ = "project_types"


class ExpenseCategory(_LookupMixin, BaseModel):
    __tablename__ = "expense_categories"


class ProductionStage(_LookupMixin, BaseModel):
    __tablename__ = "production_stages"
