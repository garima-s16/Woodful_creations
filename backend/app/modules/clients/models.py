"""Clients feature - database models.

Client is the core entity; ClientActivity, ClientDocument, and
ClientProductRate are all Client-specific sub-records, consolidated
here rather than kept as four separate one-model files."""
from datetime import datetime

from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import relationship

from app.platform.database.base import BaseModel


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
    # see app/platform/database/id_generator.generate_business_id. Never client-supplied.
    # NOT NULL: every client must have one, matching the database-level
    # constraint enforced by migration 0007's backfill.
    business_id = Column(String(10), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False, index=True)
    # Mandatory - controlled value ("Individual" / "Business"), same
    # list in UI and Excel. Defaults existing rows to "Individual" via
    # migration 0055's backfill.
    client_type = Column(String(20), nullable=False, default="Individual")
    contact_person = Column(String(255), nullable=True)  # who to actually call, when the client is a company/family, not an individual
    # Mandatory - a client record with no way to reach them isn't
    # usable. Format is validated server-side, see schemas.py.
    phone = Column(String(20), nullable=False, index=True)
    alternate_phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)  # billing address
    site_address = Column(Text, nullable=True)  # where the work actually happens, when different from the billing address
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    pincode = Column(String(10), nullable=True)
    gstin = Column(String(20), nullable=True)
    status = Column(String(20), nullable=False, default="Active")  # Active / Inactive
    lead_source = Column(String(100), nullable=True)
    first_contact_date = Column(DateTime, nullable=True)
    remarks = Column(Text, nullable=True)

    orders = relationship("Order", back_populates="client")
    documents = relationship("ClientDocument", back_populates="client", cascade="all, delete-orphan")


class ClientActivity(BaseModel):
    """A logged interaction/communication with a client - call, meeting,
    email, note, site visit, etc. Manually recorded, not auto-generated -
    this is a communication log, not an audit trail."""
    __tablename__ = "client_activities"

    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    activity_type = Column(String(30), nullable=False)  # Call/Meeting/Email/Site Visit/Note
    date = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    summary = Column(Text, nullable=False)
    logged_by = Column(String(255), nullable=True)
    follow_up_date = Column(DateTime, nullable=True, index=True)
    # Lets a resolved follow-up drop out of the pending-follow-ups list
    # instead of resurfacing forever. Irrelevant when follow_up_date is
    # unset (a plain note/log entry has nothing to "complete").
    follow_up_done = Column(Boolean, nullable=False, default=False)

    client = relationship("Client")


class ClientDocument(BaseModel):
    """A file attached to a client record - contracts, ID proofs, site
    photos. stored_filename is a random, server-generated name (never
    the user-supplied original), matching the same path-traversal
    protection established for candidate resumes.

    storage_backend/drive_file_id support both local disk and Google
    Drive storage - see GenericDocument for the same pattern applied to
    order-level documents."""
    __tablename__ = "client_documents"

    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False, unique=True)
    content_type = Column(String(100), nullable=True)
    description = Column(String(255), nullable=True)
    uploaded_by = Column(String(100), nullable=True)
    storage_backend = Column(String(20), nullable=False, default="local")
    drive_file_id = Column(String(255), nullable=True, index=True)

    client = relationship("Client", back_populates="documents")


class ClientProductRate(BaseModel):
    """A customer-specific commercial override for one Product - never
    modifies the global Product.selling_price/margin_percent or any
    RateCard; this is a separate, additive layer (per the client's own
    pricing requirements: "A customer-specific negotiated rate must NOT
    modify the global Rate Master... Global rate remains Rs 10,000").

    Exactly one of (margin_percent, fixed_selling_price) is expected to
    be set - margin_percent overrides just the margin (letting cost
    changes still flow through), fixed_selling_price is a direct
    negotiated number that ignores cost/margin entirely. Both stay
    nullable rather than an enum + single value column, since either
    is a legitimate, independently useful override shape.
    """
    __tablename__ = "client_product_rates"
    __table_args__ = (UniqueConstraint("client_id", "product_id", name="uq_client_product_rate"),)
    # Note: this constraint does NOT prevent two client-wide rows
    # (product_id=NULL) for the same client - SQL treats NULL as
    # distinct from NULL in a unique constraint. The create route
    # enforces "at most one client-wide default per client" at the
    # application level instead.

    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    # Nullable: a row with product_id=None is a CLIENT-WIDE default
    # margin (e.g. "Meenal gets 15% on everything"), distinct from a
    # row with a specific product_id, which overrides just that one
    # product for that one client. The resolution lookup checks the
    # specific-product row first, then falls back to the client-wide
    # row - see routes.py's resolve_pricing.
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)

    margin_percent = Column(Numeric(5, 2), nullable=True)  # customer-specific margin override
    fixed_selling_price = Column(Numeric(12, 2), nullable=True)  # direct negotiated price override

    notes = Column(Text, nullable=True)
    created_by = Column(String(255), nullable=True)

    client = relationship("Client")
    product = relationship("Product")
