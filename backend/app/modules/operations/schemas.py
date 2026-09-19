"""Operations domain Pydantic schemas."""
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import Optional, List
from decimal import Decimal
from datetime import datetime
from datetime import time
from app.modules.operations.models import DailyTask, TaskComment, WorkCentre, ProductionJob, ProductionOperation, Issue, Milestone, ProjectExpense, CuttingRequirement, DAILY_TASK_STATUSES, DAILY_TASK_PRIORITIES, PRODUCTION_JOB_STATUSES, PRODUCTION_OPERATION_STATUSES

# Security-hardening constants (strict input validation pass) - same
# convention as app/modules/sales/schemas.py and
# app/modules/clients/services.py.
_SHORT_TEXT_MAX = 200
_MEDIUM_TEXT_MAX = 500
_LONG_TEXT_MAX = 5000
_MAX_LINE_ITEMS = 500


class DailyTaskBase(BaseModel):
    task_code: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)  # server-generated on create, ignored if supplied
    date: datetime
    employee_id: int
    order_id: Optional[int] = None
    order_item_id: Optional[int] = None
    task_description: str = Field(..., min_length=1, max_length=_LONG_TEXT_MAX)
    task_category: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)
    priority: Optional[str] = None
    planned_start: Optional[time] = None
    planned_end: Optional[time] = None
    status: str = "TO DO"
    completion_percent: int = 0
    checked_by: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)
    delay_reason: Optional[str] = Field(default=None, max_length=_LONG_TEXT_MAX)
    remarks: Optional[str] = Field(default=None, max_length=_LONG_TEXT_MAX)
    created_by: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)
    parent_task_id: Optional[int] = None
    # Optional on create - when omitted and order_id is set, the API
    # inherits the Order's delivery_date automatically.
    # When supplied explicitly, the task-specific date takes over and
    # due_date_overridden is set so a later Order due-date change won't
    # silently overwrite it (B8).
    due_date: Optional[datetime] = None


class DailyTaskCreate(DailyTaskBase):
    # Request body, not the shared Base (which DailyTaskResponse also
    # extends) - rejecting unexpected keys here has no effect on what a
    # response can contain.
    model_config = ConfigDict(extra="forbid")

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: str) -> str:
        v = (v or "").strip()
        if v not in DAILY_TASK_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(sorted(DAILY_TASK_STATUSES))}")
        return v

    @field_validator("priority")
    @classmethod
    def priority_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return v
        v = v.strip()
        if v not in DAILY_TASK_PRIORITIES:
            raise ValueError(f"Priority must be one of: {', '.join(sorted(DAILY_TASK_PRIORITIES))}")
        return v

    @field_validator("completion_percent")
    @classmethod
    def completion_percent_in_range(cls, v: int) -> int:
        if v < 0 or v > 100:
            raise ValueError("Completion percent must be between 0 and 100")
        return v


class DailyTaskUpdate(BaseModel):
    """Master may change any of these fields. Normal (non-master) users
    are further restricted server-side to a small self-service subset
    (see EMPLOYEE_SELF_SERVICE_FIELDS in the daily-tasks route) and only
    on their own assigned task."""
    employee_id: Optional[int] = None
    order_id: Optional[int] = None
    order_item_id: Optional[int] = None
    date: Optional[datetime] = None
    task_description: Optional[str] = Field(default=None, max_length=_LONG_TEXT_MAX)
    task_category: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)
    priority: Optional[str] = None
    planned_start: Optional[time] = None
    planned_end: Optional[time] = None
    due_date: Optional[datetime] = None
    status: Optional[str] = None
    completion_percent: Optional[int] = None
    checked_by: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)
    delay_reason: Optional[str] = Field(default=None, max_length=_LONG_TEXT_MAX)
    remarks: Optional[str] = Field(default=None, max_length=_LONG_TEXT_MAX)

    model_config = ConfigDict(extra="forbid")

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if v not in DAILY_TASK_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(sorted(DAILY_TASK_STATUSES))}")
        return v

    @field_validator("priority")
    @classmethod
    def priority_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return v
        v = v.strip()
        if v not in DAILY_TASK_PRIORITIES:
            raise ValueError(f"Priority must be one of: {', '.join(sorted(DAILY_TASK_PRIORITIES))}")
        return v

    @field_validator("completion_percent")
    @classmethod
    def completion_percent_in_range(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 0 or v > 100):
            raise ValueError("Completion percent must be between 0 and 100")
        return v


class DailyTaskResponse(DailyTaskBase):
    id: int
    business_id: Optional[str] = None
    previous_task_id: Optional[int] = None
    due_date_overridden: bool = False
    actual_completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    # Denormalized, read-only context for display only - always derived
    # from the existing Order/OrderItem/Client/Employee relationships at
    # response time, never stored on DailyTask itself.
    client_name: Optional[str] = None
    order_code: Optional[str] = None
    product_name: Optional[str] = None
    employee_name: Optional[str] = None
    # True when this task's order already has a known material shortage
    # (StockService.calculate_at_risk_orders) - only populated on the
    # list endpoint, which computes this once for the whole page rather
    # than per task; single-task responses (create/update) leave this
    # at its default rather than paying for the bulk check on every
    # write, where the value is disproportionate to the cost.
    material_at_risk: bool = False

    class Config:
        from_attributes = True


class CompleteAndAssignNext(BaseModel):
    """"Complete & Assign Next" - completes the current task and
    creates a new, linked one, preserving the handoff chain rather than
    overwriting the original. Order/Order Item context and due date are
    inherited from the task being completed unless explicitly overridden
    here."""
    next_employee_id: int
    next_task_description: str = Field(..., min_length=1, max_length=_LONG_TEXT_MAX)
    next_due_date: Optional[datetime] = None
    next_order_id: Optional[int] = None
    next_order_item_id: Optional[int] = None
    next_priority: Optional[str] = None
    note: Optional[str] = Field(default=None, max_length=_LONG_TEXT_MAX)

    model_config = ConfigDict(extra="forbid")

    @field_validator("next_priority")
    @classmethod
    def next_priority_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return v
        v = v.strip()
        if v not in DAILY_TASK_PRIORITIES:
            raise ValueError(f"Priority must be one of: {', '.join(sorted(DAILY_TASK_PRIORITIES))}")
        return v


class TaskCommentCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=_LONG_TEXT_MAX)

    model_config = ConfigDict(extra="forbid")


class TaskCommentResponse(BaseModel):
    id: int
    task_id: int
    author: str
    text: str
    date: datetime

    class Config:
        from_attributes = True


class ProductionJobBase(BaseModel):
    job_code: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)  # server-generated on create, ignored if supplied
    date: datetime
    machine: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)
    employee_id: Optional[int] = None
    order_id: Optional[int] = None
    operation: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)
    stage: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)
    material_id: Optional[int] = None
    planned_qty: int = 0
    completed_qty: int = 0
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    status: str = "Not Started"
    remarks: Optional[str] = Field(default=None, max_length=_LONG_TEXT_MAX)
    blocker_reason: Optional[str] = Field(default=None, max_length=_LONG_TEXT_MAX)


class ProductionJobCreate(ProductionJobBase):
    # Request body, not the shared Base (which ProductionJobResponse also
    # extends) - rejecting unexpected keys here has no effect on what a
    # response can contain.
    model_config = ConfigDict(extra="forbid")

    @field_validator("planned_qty")
    @classmethod
    def planned_qty_not_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Planned quantity cannot be negative")
        return v

    @field_validator("completed_qty")
    @classmethod
    def completed_qty_not_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Completed quantity cannot be negative")
        return v

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: str) -> str:
        v = (v or "").strip()
        if v not in PRODUCTION_JOB_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(sorted(PRODUCTION_JOB_STATUSES))}")
        return v

    @model_validator(mode="after")
    def completed_cannot_exceed_planned(self):
        if self.completed_qty > self.planned_qty:
            raise ValueError(
                f"Completed quantity ({self.completed_qty}) cannot exceed planned quantity ({self.planned_qty})"
            )
        return self


class ProductionJobUpdate(BaseModel):
    completed_qty: Optional[int] = None
    status: Optional[str] = None
    stage: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)
    remarks: Optional[str] = Field(default=None, max_length=_LONG_TEXT_MAX)
    blocker_reason: Optional[str] = Field(default=None, max_length=_LONG_TEXT_MAX)

    model_config = ConfigDict(extra="forbid")

    @field_validator("completed_qty")
    @classmethod
    def completed_qty_not_negative(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Completed quantity cannot be negative")
        return v

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if v not in PRODUCTION_JOB_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(sorted(PRODUCTION_JOB_STATUSES))}")
        return v


class ProductionJobResponse(ProductionJobBase):
    id: int
    business_id: Optional[str] = None
    completion_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductionOperationBase(BaseModel):
    production_job_id: int
    sequence: int = 1
    operation_name: str = Field(..., min_length=1, max_length=_SHORT_TEXT_MAX)
    description: Optional[str] = Field(default=None, max_length=_LONG_TEXT_MAX)
    resource: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)
    work_centre_id: Optional[int] = None
    estimated_duration_minutes: Optional[int] = None
    actual_duration_minutes: Optional[int] = None
    status: str = "Not Started"
    depends_on_operation_id: Optional[int] = None
    employee_id: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class ProductionOperationCreate(ProductionOperationBase):
    # Request body, not the shared Base (which ProductionOperationResponse
    # also extends) - rejecting unexpected keys here has no effect on what
    # a response can contain.
    model_config = ConfigDict(extra="forbid")

    @field_validator("sequence")
    @classmethod
    def sequence_must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Sequence must be at least 1")
        return v

    @field_validator("estimated_duration_minutes", "actual_duration_minutes")
    @classmethod
    def duration_not_negative(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Duration cannot be negative")
        return v

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: str) -> str:
        v = (v or "").strip()
        if v not in PRODUCTION_OPERATION_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(sorted(PRODUCTION_OPERATION_STATUSES))}")
        return v


class ProductionOperationUpdate(BaseModel):
    status: Optional[str] = None
    actual_duration_minutes: Optional[int] = None
    resource: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)
    employee_id: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("actual_duration_minutes")
    @classmethod
    def duration_not_negative(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Duration cannot be negative")
        return v

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if v not in PRODUCTION_OPERATION_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(sorted(PRODUCTION_OPERATION_STATUSES))}")
        return v


class ProductionOperationResponse(ProductionOperationBase):
    id: int
    business_id: Optional[str] = None
    is_blocked_by_dependency: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkCentreCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=_SHORT_TEXT_MAX)
    type: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)
    is_active: bool = True
    capacity_hours_per_day: Optional[Decimal] = None
    notes: Optional[str] = Field(default=None, max_length=_LONG_TEXT_MAX)

    model_config = ConfigDict(extra="forbid")

    @field_validator("capacity_hours_per_day")
    @classmethod
    def capacity_not_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Capacity cannot be negative")
        return v


class WorkCentreUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)
    type: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)
    is_active: Optional[bool] = None
    capacity_hours_per_day: Optional[Decimal] = None
    notes: Optional[str] = Field(default=None, max_length=_LONG_TEXT_MAX)

    model_config = ConfigDict(extra="forbid")

    @field_validator("capacity_hours_per_day")
    @classmethod
    def capacity_not_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Capacity cannot be negative")
        return v


class WorkCentreResponse(BaseModel):
    id: int
    business_id: Optional[str] = None
    name: str
    type: Optional[str] = None
    is_active: bool
    capacity_hours_per_day: Optional[Decimal] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class IssueBase(BaseModel):
    issue_code: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)  # server-generated on create, ignored if supplied
    date: datetime
    order_id: Optional[int] = None
    material_id: int
    quantity_issued: Decimal
    unit: str = Field(..., min_length=1, max_length=_SHORT_TEXT_MAX)
    issued_to: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)
    department: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)
    purpose: Optional[str] = Field(default=None, max_length=_LONG_TEXT_MAX)
    approved_by: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)
    remarks: Optional[str] = Field(default=None, max_length=_LONG_TEXT_MAX)
    location_id: Optional[int] = None  # which location to issue from; falls back to the material's primary location if omitted


class IssueCreate(IssueBase):
    # Request body, not the shared Base (which IssueResponse also
    # extends) - rejecting unexpected keys here has no effect on what a
    # response can contain.
    model_config = ConfigDict(extra="forbid")


class IssueResponse(IssueBase):
    id: int
    rate_at_issue: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MilestoneBase(BaseModel):
    order_id: int
    name: str = Field(..., min_length=1, max_length=_SHORT_TEXT_MAX)
    target_date: Optional[datetime] = None
    remarks: Optional[str] = Field(default=None, max_length=_LONG_TEXT_MAX)


class MilestoneCreate(MilestoneBase):
    # Request body, not the shared Base (which MilestoneResponse also
    # extends) - rejecting unexpected keys here has no effect on what a
    # response can contain.
    model_config = ConfigDict(extra="forbid")


class MilestoneUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)
    target_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    remarks: Optional[str] = Field(default=None, max_length=_LONG_TEXT_MAX)

    model_config = ConfigDict(extra="forbid")


class MilestoneResponse(MilestoneBase):
    id: int
    business_id: Optional[str] = None
    completed_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectExpenseBase(BaseModel):
    expense_code: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)  # server-generated on create, ignored if supplied
    date: datetime
    order_id: int
    category: str = Field(..., min_length=1, max_length=_SHORT_TEXT_MAX)
    description: Optional[str] = Field(default=None, max_length=_LONG_TEXT_MAX)
    paid_to: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)
    amount: Decimal
    approved_by: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)
    remarks: Optional[str] = Field(default=None, max_length=_LONG_TEXT_MAX)


class ProjectExpenseCreate(ProjectExpenseBase):
    # Request body, not the shared Base (which ProjectExpenseResponse also
    # extends) - rejecting unexpected keys here has no effect on what a
    # response can contain.
    model_config = ConfigDict(extra="forbid")

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Amount must be greater than zero")
        return v


class ProjectExpenseUpdate(BaseModel):
    category: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)
    description: Optional[str] = Field(default=None, max_length=_LONG_TEXT_MAX)
    paid_to: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)
    amount: Optional[Decimal] = None
    approved_by: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)
    remarks: Optional[str] = Field(default=None, max_length=_LONG_TEXT_MAX)

    model_config = ConfigDict(extra="forbid")

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v <= 0:
            raise ValueError("Amount must be greater than zero")
        return v


class ProjectExpenseResponse(ProjectExpenseBase):
    id: int
    business_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CuttingRequirementBase(BaseModel):
    production_job_id: int
    product_id: Optional[int] = None
    material_id: int
    part_name: str = Field(..., min_length=1, max_length=_SHORT_TEXT_MAX)
    quantity: int = 1
    length_mm: Decimal
    width_mm: Decimal
    thickness_mm: Optional[Decimal] = None
    grain_direction: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)
    rotation_allowed: bool = True
    kerf_mm: Optional[Decimal] = None
    notes: Optional[str] = Field(default=None, max_length=_LONG_TEXT_MAX)


class CuttingRequirementCreate(CuttingRequirementBase):
    # Request body, not the shared Base (which CuttingRequirementResponse
    # also extends) - rejecting unexpected keys here has no effect on what
    # a response can contain.
    model_config = ConfigDict(extra="forbid")

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Quantity must be at least 1")
        return v

    @field_validator("length_mm", "width_mm")
    @classmethod
    def dimension_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Dimensions must be greater than zero")
        return v

    @field_validator("thickness_mm", "kerf_mm")
    @classmethod
    def optional_dimension_not_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v <= 0:
            raise ValueError("If given, this must be greater than zero")
        return v


class CuttingRequirementUpdate(BaseModel):
    part_name: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)
    quantity: Optional[int] = None
    length_mm: Optional[Decimal] = None
    width_mm: Optional[Decimal] = None
    thickness_mm: Optional[Decimal] = None
    grain_direction: Optional[str] = Field(default=None, max_length=_SHORT_TEXT_MAX)
    rotation_allowed: Optional[bool] = None
    kerf_mm: Optional[Decimal] = None
    notes: Optional[str] = Field(default=None, max_length=_LONG_TEXT_MAX)

    model_config = ConfigDict(extra="forbid")

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError("Quantity must be at least 1")
        return v

    @field_validator("length_mm", "width_mm")
    @classmethod
    def dimension_must_be_positive(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v <= 0:
            raise ValueError("Dimensions must be greater than zero")
        return v


class CuttingRequirementResponse(CuttingRequirementBase):
    id: int
    business_id: Optional[str] = None
    material_name: Optional[str] = None
    product_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
