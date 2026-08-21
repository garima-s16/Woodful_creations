from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


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
