"""Shop-floor operations domain models: DailyTask, TaskComment,
ProductionJob, Issue, Milestone, ProjectExpense.

Consolidated from daily_task.py + production_job.py + issue.py +
milestone.py + project_expense.py. These are
independent small tables that all hang off Order/Employee/Material and
are consumed together by the operations/production feature area.
"""
from datetime import datetime

from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, DateTime, Time, Text, Boolean
from sqlalchemy.orm import relationship
from app.platform.database.base import BaseModel


class DailyTask(BaseModel):
    """Daily Employee Task Management."""
    __tablename__ = "daily_tasks"

    task_code = Column(String(20), unique=True, nullable=False, index=True)  # TSK-001
    # Opaque 10-char external identifier (e.g. A7K92P4XQ1) - separate from
    # task_code, which stays as the human-scannable sequential reference.
    business_id = Column(String(10), unique=True, index=True, nullable=True)
    date = Column(DateTime, nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    # Optional link to the specific Order Item/Product a task
    # concerns, so a task can say "Bedroom Wardrobe" rather than just
    # "Ishu's order". Reuses the existing OrderItem/Product relationships -
    # never duplicates client/order/product data onto DailyTask itself.
    order_item_id = Column(Integer, ForeignKey("order_items.id"), nullable=True, index=True)
    task_description = Column(String(500), nullable=False)
    task_category = Column(String(50), nullable=True)  # e.g. Cutting/Assembly/Installation - distinct from the free-text description
    priority = Column(String(20), nullable=True)
    planned_start = Column(Time, nullable=True)
    planned_end = Column(Time, nullable=True)
    status = Column(String(20), nullable=False, default="TO DO", index=True)
    completion_percent = Column(Integer, nullable=False, default=0)
    actual_completed_at = Column(DateTime, nullable=True)  # set when the task is actually marked DONE, not merely planned_end
    checked_by = Column(String(255), nullable=True)
    delay_reason = Column(String(255), nullable=True)  # doubles as the "blocked" reason
    remarks = Column(Text, nullable=True)
    created_by = Column(String(255), nullable=True)
    parent_task_id = Column(Integer, ForeignKey("daily_tasks.id"), nullable=True, index=True)
    previous_task_id = Column(Integer, ForeignKey("daily_tasks.id"), nullable=True, index=True)
    # The date by which the work must be completed,
    # distinct from `date` (when the task is planned/assigned). Defaults to
    # the parent Order's delivery_date at creation time when the task is
    # linked to an order; due_date_overridden tracks whether a Master has
    # since set a task-specific deadline, so a later Order due-date change
    # only propagates to tasks that were never explicitly overridden.
    due_date = Column(DateTime, nullable=True, index=True)
    due_date_overridden = Column(Boolean, nullable=False, default=False)

    employee = relationship("Employee", back_populates="daily_tasks")
    order = relationship("Order", back_populates="daily_tasks")
    order_item = relationship("OrderItem")
    parent_task = relationship("DailyTask", remote_side="DailyTask.id", foreign_keys=[parent_task_id])
    previous_task = relationship("DailyTask", remote_side="DailyTask.id", foreign_keys=[previous_task_id])


class TaskComment(BaseModel):
    """Simple comment on a task - practical shop-floor communication
    ("Laminate received, ready for cutting"), not a full collaboration
    platform."""
    __tablename__ = "task_comments"

    task_id = Column(Integer, ForeignKey("daily_tasks.id"), nullable=False, index=True)
    author = Column(String(255), nullable=False)
    text = Column(Text, nullable=False)
    date = Column(DateTime, nullable=False)

    task = relationship("DailyTask")


class ProductionJob(BaseModel):
    """Production & Machine Job Tracker."""
    __tablename__ = "production_jobs"

    job_code = Column(String(20), unique=True, nullable=False, index=True)  # JOB-001
    # Opaque 10-char external identifier (e.g. A7K92P4XQ1) - separate from
    # job_code, which stays as the human-scannable sequential reference.
    business_id = Column(String(10), unique=True, index=True, nullable=True)
    date = Column(DateTime, nullable=False, index=True)
    machine = Column(String(100), nullable=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)  # operator
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    operation = Column(String(255), nullable=True)
    stage = Column(String(50), nullable=True)  # Cutting/CNC.../Assembly/.../Dispatch - standardized, distinct from the free-text operation description
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=True, index=True)
    planned_qty = Column(Integer, nullable=False, default=0)
    completed_qty = Column(Integer, nullable=False, default=0)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    status = Column(String(20), nullable=False, default="Not Started", index=True)
    completion_date = Column(DateTime, nullable=True)  # set when the job actually transitions to Completed
    remarks = Column(Text, nullable=True)
    blocker_reason = Column(Text, nullable=True)  # set when status="Blocked" - why, matching DailyTask.delay_reason's role

    employee = relationship("Employee")
    order = relationship("Order", back_populates="production_jobs")
    material = relationship("Material")


class Issue(BaseModel):
    """Stock Out / Material Issue Register."""
    __tablename__ = "issues"

    issue_code = Column(String(20), unique=True, nullable=False, index=True)  # ISS-001
    date = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)
    quantity_issued = Column(Numeric(12, 2), nullable=False)
    unit = Column(String(20), nullable=False)
    issued_to = Column(String(255), nullable=True)
    department = Column(String(100), nullable=True)
    purpose = Column(String(255), nullable=True)
    approved_by = Column(String(255), nullable=True)
    remarks = Column(Text, nullable=True)
    # Which location this material was issued from. Nullable - unset means
    # "the material's primary location", preserving behavior for existing
    # callers that don't pass one.
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True, index=True)
    # The material's average_rate at the moment this issue was recorded,
    # frozen here permanently - a later
    # purchase changing the material's current average_rate must never
    # retroactively change what this issue is understood to have cost.
    # Nullable only for rows that predate this column (see migration
    # 0064's backfill note - the true historical rate for those is
    # genuinely unknown, so NULL means "unknown", not zero).
    rate_at_issue = Column(Numeric(12, 2), nullable=True)

    order = relationship("Order", back_populates="issues")
    material = relationship("Material", back_populates="issues")
    location = relationship("Location")


class Milestone(BaseModel):
    """A named, date-bearing checkpoint within a project (Order) -
    "Design approval", "Material delivery expected", "Installation
    target" - distinct from Order.project_status, which already tracks
    the detailed production phase itself. Deliberately lightweight:
    name, target date, completion, and an optional note - not a
    separate workflow state machine."""
    __tablename__ = "milestones"

    business_id = Column(String(10), unique=True, index=True, nullable=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    target_date = Column(DateTime, nullable=True)
    completed_date = Column(DateTime, nullable=True)
    remarks = Column(Text, nullable=True)

    order = relationship("Order", back_populates="milestones")


class ProjectExpense(BaseModel):
    """Order-wise Expense Register - feeds Order Profitability."""
    __tablename__ = "project_expenses"

    expense_code = Column(String(20), unique=True, nullable=False, index=True)  # EXP-001
    # Opaque 10-char external identifier (e.g. A7K92P4XQ1) - separate from
    # expense_code, which stays as the human-scannable sequential reference.
    business_id = Column(String(10), unique=True, index=True, nullable=True)
    date = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    category = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    paid_to = Column(String(255), nullable=True)
    amount = Column(Numeric(12, 2), nullable=False, default=0)
    approved_by = Column(String(255), nullable=True)
    remarks = Column(Text, nullable=True)

    order = relationship("Order", back_populates="expenses")
