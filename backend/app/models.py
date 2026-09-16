"""Top-level Setting lookup models, plus the master model-
registration import list ensuring every SQLAlchemy model across all
domains is registered with Base.metadata (required for
create_all()/Alembic autogenerate). Combines the former setting.py
and __init__.py."""
from app.platform.database import Base, BaseModel
from app.platform.ids import IdSequence
from app.modules.auth.auth import User, PasswordResetToken
from app.modules.communications.models import Notification
from app.modules.procurement.models import PersonalCartItem
from app.modules.inventory.models import Location, MaterialCategory, MaterialSubcategory, MaterialAttributeDefinition, MaterialAttributeValue, Material
from app.modules.procurement.models import Supplier, SupplierMaterial, ProcurementRequirement, SupplierDecision
from app.modules.catalog.models import Product, ProductMaterial, RateCard
from app.modules.inventory.models import StockTransfer, StockAdjustment
from app.modules.procurement.models import Purchase
from app.modules.operations.models import Issue, Milestone, DailyTask, TaskComment, ProductionJob, WorkCentre, ProductionOperation, CuttingRequirement
from app.modules.clients.models import Client, ClientActivity, ClientDocument, ClientProductRate
from app.modules.sales.models import Order, OrderItem, OrderComment, Payment, PaymentDocument, Estimate, EstimateLineItem
from app.modules.operations.models import ProjectExpense
from app.modules.hr.models import Employee, Attendance, Leave, SalarySlip, WorkingCalendarSettings, CompanyHoliday, SalaryAdvance
from app.modules.reporting.services import AIWorkspaceReport
from app.modules.documents.api import GenericDocument
from app.modules.ai.contracts import ChatLearningCandidate
from app.modules.reporting.services import ReportHistory
from app.modules.inventory.models import StockLedgerEntry
from app.modules.recruitment.module import Candidate, Interview
from app.platform.audit import AuditLog
from app.modules.communications.models import AutomationLog
from sqlalchemy import Column, String
from app.platform.database import BaseModel


class _LookupMixin:
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(255), nullable=True)


class Unit(_LookupMixin, BaseModel):
    __tablename__ = "units"


class StockStatus(_LookupMixin, BaseModel):
    __tablename__ = "stock_statuses"


class StockPaymentStatus(_LookupMixin, BaseModel):
    __tablename__ = "stock_payment_statuses"


class SupplierTerm(_LookupMixin, BaseModel):
    __tablename__ = "supplier_terms"


class Department(_LookupMixin, BaseModel):
    __tablename__ = "departments"


class TaskStatus(_LookupMixin, BaseModel):
    __tablename__ = "task_statuses"


class AttendanceStatus(_LookupMixin, BaseModel):
    __tablename__ = "attendance_statuses"


class Machine(_LookupMixin, BaseModel):
    __tablename__ = "machines"


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


# --- __init__.py body (model registration imports above) ---
__all__ = [
    "Base", "BaseModel", "IdSequence", "User", "Notification", "PersonalCartItem",
    "Unit", "MaterialCategory", "StockStatus", "StockPaymentStatus", "Location", "SupplierTerm",
    "Department", "TaskStatus", "AttendanceStatus", "Machine",
    "ProjectStatus", "Priority", "PaymentMode", "LeadSource", "ProjectType", "ExpenseCategory", "ProductionStage",
    "Supplier", "Material", "MaterialCategory", "MaterialSubcategory", "SupplierMaterial", "Product", "ProductMaterial",
    "RateCard",
    "ClientProductRate",
    "Location",
    "MaterialAttributeDefinition", "MaterialAttributeValue", "Purchase", "Issue", "StockTransfer", "StockAdjustment",
    "Client", "ClientActivity", "Order", "OrderItem", "Payment", "ProjectExpense", "Estimate", "EstimateLineItem",
    "Employee", "Attendance", "Leave", "DailyTask", "TaskComment", "OrderComment", "AIWorkspaceReport", "ProductionJob", "SalarySlip",
    "WorkingCalendarSettings", "CompanyHoliday", "PasswordResetToken", "Milestone", "ClientDocument", "PaymentDocument",
    "GenericDocument", "StockLedgerEntry",
    "Candidate", "Interview",
    "AuditLog", "AutomationLog",
    "SalaryAdvance", "WorkCentre", "ProductionOperation", "ProcurementRequirement", "SupplierDecision", "CuttingRequirement",
]
