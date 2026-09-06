"""Shop-floor operations domain models: DailyTask, TaskComment,
ProductionJob, ProductionOperation, WorkCentre, CuttingRequirement,
Issue, Milestone, ProjectExpense.

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


class WorkCentre(BaseModel):
    """A configurable production resource (P0.3.5) - CNC, Cutting, Edge
    Banding, Assembly, Finishing, or any other resource this business
    actually has, never a hardcoded list. capacity_hours_per_day is a
    simple, honest daily-capacity figure - not a full working-calendar
    system (holidays, shift patterns, per-day overrides), which this
    codebase has no existing model for and which P0.3.6's capacity
    check does not yet need; building one now would be exactly the
    "fabricated architecture" the brief warns against."""
    __tablename__ = "work_centres"

    business_id = Column(String(10), unique=True, index=True, nullable=True)
    name = Column(String(100), nullable=False, unique=True)
    type = Column(String(50), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    capacity_hours_per_day = Column(Numeric(5, 2), nullable=True)
    notes = Column(Text, nullable=True)


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
    blocker_reason = Column(Text, nullable=True)  # freestanding - can accompany any status, not tied to a "Blocked" status value (there isn't one; see PRODUCTION_JOB_STATUSES in schemas.py)

    employee = relationship("Employee")
    order = relationship("Order", back_populates="production_jobs")
    material = relationship("Material")
    operations = relationship("ProductionOperation", back_populates="production_job",
                               cascade="all, delete-orphan", order_by="ProductionOperation.sequence")


class ProductionOperation(BaseModel):
    """A single manufacturing step within a ProductionJob (P0.3.3/3.4) -
    e.g. Cutting -> CNC -> Edge Banding -> Assembly -> Finishing.
    Deliberately a simple, linear dependency (depends_on_operation_id,
    at most one predecessor) rather than a general workflow/DAG engine -
    matches every dependency example the spec gives (a strictly ordered
    chain) and its explicit "do not build an unnecessarily complex
    workflow engine".

    resource is free text for now, matching ProductionJob.machine's
    existing convention - work_centre_id below is the newer, optional
    link to a real, configured WorkCentre (P0.3.5); both exist
    side by side so operations recorded before WorkCentre existed
    remain valid without a backfill."""
    __tablename__ = "production_operations"

    production_job_id = Column(Integer, ForeignKey("production_jobs.id"), nullable=False, index=True)
    sequence = Column(Integer, nullable=False, default=1)
    operation_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    resource = Column(String(100), nullable=True)
    work_centre_id = Column(Integer, ForeignKey("work_centres.id"), nullable=True, index=True)
    estimated_duration_minutes = Column(Integer, nullable=True)
    actual_duration_minutes = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, default="Not Started", index=True)
    depends_on_operation_id = Column(Integer, ForeignKey("production_operations.id"), nullable=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)

    production_job = relationship("ProductionJob", back_populates="operations")
    depends_on = relationship("ProductionOperation", remote_side="ProductionOperation.id")
    employee = relationship("Employee")
    work_centre = relationship("WorkCentre")

    @property
    def is_blocked_by_dependency(self):
        """True only when this operation has a real predecessor that is
        not yet Completed - never a fabricated block. An operation with
        no predecessor is never blocked by this check."""
        return bool(self.depends_on_operation_id) and self.depends_on is not None and self.depends_on.status != "Completed"


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


class CuttingRequirement(BaseModel):
    """A single part that needs to be cut from a material sheet (P0.3
    section 25) - one row per part, not a single lump quantity, so
    each part's own dimensions/grain/rotation constraint is tracked
    individually rather than collapsed into free text (the brief's own
    "do not store critical cutting data only as free text"). Creating
    this record does NOT touch physical stock - it is a plan, not a
    consumption event; StockService.record_issue (via Issue) remains
    the only path that actually reduces Material.current_stock, kept
    completely separate on purpose.

    Real dimensions in millimetres (length/width), not a vague "size"
    string. thickness_mm is optional since it's frequently already
    implied by the chosen material (Material.thickness_size), not
    duplicated here unless a part genuinely needs a different
    thickness recorded. grain_direction/rotation_allowed exist because
    a part that must keep its grain aligned genuinely cannot be
    freely rotated 90 degrees when nested onto a sheet - this is
    real, structural information a nesting algorithm needs, not
    decoration."""
    __tablename__ = "cutting_requirements"

    business_id = Column(String(10), unique=True, index=True, nullable=True)
    production_job_id = Column(Integer, ForeignKey("production_jobs.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)
    part_name = Column(String(255), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    length_mm = Column(Numeric(10, 2), nullable=False)
    width_mm = Column(Numeric(10, 2), nullable=False)
    thickness_mm = Column(Numeric(10, 2), nullable=True)
    # "Length" / "Width" / "None" - free text like ProductionJob.machine's
    # existing convention (a fixed grain-direction enum would need to
    # anticipate every material type up front; this business decides
    # its own vocabulary instead), but never left implicit in a
    # description field, which is the actual brief requirement.
    grain_direction = Column(String(20), nullable=True)
    rotation_allowed = Column(Boolean, nullable=False, default=True)
    kerf_mm = Column(Numeric(6, 2), nullable=True)
    notes = Column(Text, nullable=True)

    production_job = relationship("ProductionJob")
    product = relationship("Product")
    material = relationship("Material")
