from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Time, Text
from sqlalchemy.orm import relationship
from datetime import datetime
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
    priority = Column(String(20), nullable=True)
    planned_start = Column(Time, nullable=True)
    planned_end = Column(Time, nullable=True)
    status = Column(String(20), nullable=False, default="Not Started", index=True)
    completion_percent = Column(Integer, nullable=False, default=0)
    checked_by = Column(String(255), nullable=True)
    delay_reason = Column(String(255), nullable=True)
    remarks = Column(Text, nullable=True)

    employee = relationship("Employee", back_populates="daily_tasks")
    order = relationship("Order", back_populates="daily_tasks")
