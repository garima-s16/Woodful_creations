from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


class Order(BaseModel):
    """Order & Project Management. total_received/balance are derived from
    advance + other_received (kept as stored columns for fast dashboard
    reads, maintained transactionally by OrderService alongside Payments)."""
    __tablename__ = "orders"

    order_code = Column(String(20), unique=True, nullable=False, index=True)  # WC-2026-001
    # Opaque 10-char external identifier (e.g. A7K92P4XQ1) - separate from
    # order_code, which stays as the human-scannable sequential reference.
    business_id = Column(String(10), unique=True, index=True, nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    project_type = Column(String(100), nullable=True)
    order_date = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    delivery_date = Column(DateTime, nullable=True)
    order_value = Column(Numeric(12, 2), nullable=False, default=0)
    advance = Column(Numeric(12, 2), nullable=False, default=0)
    other_received = Column(Numeric(12, 2), nullable=False, default=0)
    total_received = Column(Numeric(12, 2), nullable=False, default=0)
    balance = Column(Numeric(12, 2), nullable=False, default=0)
    project_status = Column(String(50), nullable=False, default="Enquiry", index=True)
    design_status = Column(String(50), nullable=False, default="Pending")
    execution_status = Column(String(50), nullable=False, default="Pending")
    delivery_status = Column(String(50), nullable=False, default="Pending")
    progress_percent = Column(Integer, nullable=False, default=0)
    priority = Column(String(20), nullable=True)
    supervisor = Column(String(255), nullable=True)
    site_address = Column(Text, nullable=True)
    remarks = Column(Text, nullable=True)

    client = relationship("Client", back_populates="orders")
    payments = relationship("Payment", back_populates="order")
    expenses = relationship("ProjectExpense", back_populates="order")
    issues = relationship("Issue", back_populates="order")
    daily_tasks = relationship("DailyTask", back_populates="order")
    production_jobs = relationship("ProductionJob", back_populates="order")
    estimates = relationship("Estimate", back_populates="order")
    items = relationship("OrderItem", back_populates="order",
                          cascade="all, delete-orphan", order_by="OrderItem.sort_order")

    @property
    def items_subtotal(self):
        """Sum of item amounts if any exist; None when there are no
        items, so callers can tell "no scope entered" apart from a
        genuine zero-value order."""
        from decimal import Decimal
        if not self.items:
            return None
        return sum((item.amount or Decimal("0") for item in self.items), Decimal("0"))

    @property
    def payment_status(self):
        """Derived from balance/total_received - computed once here so
        every consumer (dashboard, PDF, Excel, chatbot, frontend) reads
        the same value rather than each working it out independently."""
        if not self.order_value:
            return "N/A"
        if self.total_received and self.total_received >= self.order_value:
            return "Paid"
        if self.total_received and self.total_received > 0:
            return "Partially Paid"
        return "Unpaid"

    def recompute_totals(self):
        """Call after adding/editing a Payment - keeps total_received and
        balance consistent with the advance recorded at order creation
        plus the sum of this order's Payment rows. The advance is stored
        directly on the order, not as its own Payment record, so it must
        be added back in explicitly here - omitting it was a real bug:
        total_received would silently drop to just the newest payment
        the moment any payment was recorded after order creation,
        making the advance disappear from the running total."""
        from decimal import Decimal
        payments_total = sum((p.amount for p in self.payments), Decimal("0")) if self.payments else Decimal("0")
        total = (self.advance or Decimal("0")) + payments_total
        self.total_received = total
        self.balance = (self.order_value or Decimal("0")) - total
