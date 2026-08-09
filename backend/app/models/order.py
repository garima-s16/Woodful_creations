from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, DateTime, Text, Date
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel

class Order(BaseModel):
    __tablename__ = "orders"
    
    order_id = Column(String(20), unique=True, nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    project_type = Column(String(100), nullable=False)
    order_date = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    delivery_date = Column(Date, nullable=True)
    order_value = Column(Numeric(12, 2), nullable=False)
    advance_payment = Column(Numeric(12, 2), default=0)
    status = Column(String(50), default="Enquiry", index=True)
    priority = Column(String(50), nullable=True)
    lead_source = Column(String(100), nullable=True)
    supervisor = Column(String(255), nullable=True)
    site_address = Column(Text, nullable=True)
    remarks = Column(Text, nullable=True)
    
    client = relationship("Client", back_populates="orders")
    expenses = relationship("OrderExpense", back_populates="order")
    payments = relationship("Payment", back_populates="order")
    material_issues = relationship("MaterialIssue", back_populates="order")
    
    def calculate_totals(self, db):
        total_received = db.query(Payment).filter(Payment.order_id == self.id).with_entities(Payment.amount).scalar() or 0
        total_expenses = db.query(OrderExpense).filter(OrderExpense.order_id == self.id).with_entities(OrderExpense.amount).scalar() or 0
        return {
            "total_received": total_received,
            "pending_payment": float(self.order_value) - float(total_received),
            "total_expenses": total_expenses,
            "gross_profit": float(self.order_value) - float(total_expenses)
        }

class OrderExpense(BaseModel):
    __tablename__ = "order_expenses"
    
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    category = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    amount = Column(Numeric(12, 2), nullable=False)
    remarks = Column(Text, nullable=True)
    
    order = relationship("Order", back_populates="expenses")
