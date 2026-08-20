from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Time, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


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

    employee = relationship("Employee", back_populates="daily_tasks")
    order = relationship("Order", back_populates="daily_tasks")
    parent_task = relationship("DailyTask", remote_side="DailyTask.id", foreign_keys=[parent_task_id])
    previous_task = relationship("DailyTask", remote_side="DailyTask.id", foreign_keys=[previous_task_id])
