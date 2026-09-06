from app.platform.database.base import Base, BaseModel
from app.platform.database.id_sequence import IdSequence
from app.modules.auth.models import User, PasswordResetToken
from app.modules.communications.models import Notification
from app.modules.procurement.models import PersonalCartItem

from app.models.setting import (
    Unit, StockStatus, StockPaymentStatus, SupplierTerm,
    Department, TaskStatus, AttendanceStatus, Machine,
    ProjectStatus, Priority, PaymentMode, LeadSource, ProjectType, ExpenseCategory, ProductionStage,
)

from app.modules.inventory.models import Location, MaterialCategory, MaterialSubcategory, MaterialAttributeDefinition, MaterialAttributeValue, Material
from app.modules.procurement.models import Supplier, SupplierMaterial
from app.modules.catalog.models import Product, ProductMaterial, RateCard
from app.modules.inventory.models import StockTransfer, StockAdjustment
from app.modules.procurement.models import Purchase
from app.modules.operations.models import Issue, Milestone, DailyTask, TaskComment, ProductionJob

from app.modules.clients.models import Client, ClientActivity, ClientDocument, ClientProductRate
from app.modules.sales.models import Order, OrderItem, OrderComment, Payment, PaymentDocument, Estimate, EstimateLineItem
from app.modules.operations.models import ProjectExpense

from app.modules.hr.models import Employee, Attendance, Leave, SalarySlip, WorkingCalendarSettings, CompanyHoliday
from app.modules.reporting.models import AIWorkspaceReport
from app.modules.documents.models import GenericDocument
from app.modules.ai.models import ChatLearningCandidate
from app.modules.reporting.models import ReportHistory
from app.modules.inventory.models import StockLedgerEntry

from app.modules.recruitment.models import Candidate, Interview

from app.platform.audit.audit import AuditLog
from app.modules.communications.models import AutomationLog

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
]
