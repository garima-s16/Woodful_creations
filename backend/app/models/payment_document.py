from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class PaymentDocument(BaseModel):
    """Proof of a payment - a scanned cheque, UPI screenshot, bank
    transfer receipt. stored_filename is a random, server-generated
    name (never the user-supplied original), matching the exact same
    path-traversal protection already established for client
    documents and candidate resumes."""
    __tablename__ = "payment_documents"

    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False, unique=True)
    content_type = Column(String(100), nullable=True)
    description = Column(String(255), nullable=True)
    uploaded_by = Column(String(100), nullable=True)

    payment = relationship("Payment", back_populates="documents")
