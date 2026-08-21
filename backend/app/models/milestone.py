from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


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
