from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Time, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


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
