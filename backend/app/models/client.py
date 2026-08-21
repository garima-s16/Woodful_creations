from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Client(BaseModel):
    """Client Master. total_orders/total_sales are derived (see
    ClientService) rather than stored, to avoid divergence from the
    orders table.

    Field selection follows the real Woodful "CLIENT MASTER" reference
    sheet (Client Code, Client/Company, Contact Person, Phone, Email,
    Billing Address, Site Address, GSTIN, Remarks) rather than a
    generic ERP field list - contact_person/site_address/gstin were
    added to match that; fields like PAN or a separate
    state/pincode/country breakdown were deliberately not added since
    neither the source material nor an existing workflow calls for them.
    """
    __tablename__ = "clients"

    client_code = Column(String(20), unique=True, nullable=False, index=True)  # CL-001
    # Centralized, incremental, system-generated 10-character external ID -
    # see app/utils/id_generator.generate_business_id. Never client-supplied.
    # NOT NULL: every client must have one, same as the database-level
    # constraint already enforced by migration 0007's backfill.
    business_id = Column(String(10), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False, index=True)
    contact_person = Column(String(255), nullable=True)  # who to actually call, when the client is a company/family, not an individual
    # Mandatory - a confirmed demo-testing finding (Client Master
    # section 3): a client record with no way to reach them isn't
    # usable. Format is validated server-side, see schemas/client.py.
    phone = Column(String(20), nullable=False, index=True)
    alternate_phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)  # billing address
    site_address = Column(Text, nullable=True)  # where the work actually happens, when different from the billing address
    city = Column(String(100), nullable=True)
    gstin = Column(String(20), nullable=True)
    status = Column(String(20), nullable=False, default="Active")  # Active / Inactive
    lead_source = Column(String(100), nullable=True)
    first_contact_date = Column(DateTime, nullable=True)
    remarks = Column(Text, nullable=True)

    orders = relationship("Order", back_populates="client")
    documents = relationship("ClientDocument", back_populates="client", cascade="all, delete-orphan")
