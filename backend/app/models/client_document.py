from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class ClientDocument(BaseModel):
    """A file attached to a client record - contracts, ID proofs, site
    photos. stored_filename is a random, server-generated name (never
    the user-supplied original), matching the same path-traversal
    protection already established for candidate resumes."""
    __tablename__ = "client_documents"

    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False, unique=True)
    content_type = Column(String(100), nullable=True)
    description = Column(String(255), nullable=True)
    uploaded_by = Column(String(100), nullable=True)

    client = relationship("Client", back_populates="documents")
