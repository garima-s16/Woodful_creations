from sqlalchemy import Column, Integer, String, Date, DateTime, Float, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from .core.db import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(128), unique=True, index=True, nullable=False)
    email = Column(String(256), unique=True, index=True, nullable=True)
    full_name = Column(String(256))
    hashed_password = Column(String(512))
    phone = Column(String(32))
    is_active = Column(Boolean, default=True)
    is_master = Column(Boolean, default=False)
    cannot_be_deleted = Column(Boolean, default=False)
    role = Column(String(64), default="user")
    created_at = Column(DateTime, default=datetime.utcnow)

class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True)
    supplier_id = Column(String(32), unique=True, index=True)
    name = Column(String(256))
    category = Column(String(128))
    contact_person = Column(String(128))
    phone = Column(String(32))
    gstin = Column(String(64))
    payment_terms = Column(String(64))
    remarks = Column(Text)

class Material(Base):
    __tablename__ = "materials"
    id = Column(Integer, primary_key=True)
    material_id = Column(String(32), unique=True, index=True)
    name = Column(String(256))
    category = Column(String(128))
    brand_grade = Column(String(128))
    thickness_size = Column(String(128))
    unit = Column(String(32))
    opening_stock = Column(Float, default=0)
    current_stock = Column(Float, default=0)
    minimum_stock = Column(Float, default=0)
    unit_cost = Column(Float, default=0)

class Purchase(Base):
    __tablename__ = "purchases"
    id = Column(Integer, primary_key=True)
    purchase_no = Column(String(64), unique=True, index=True)
    date = Column(Date)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    material_id = Column(Integer, ForeignKey("materials.id"))
    quantity = Column(Float)
    unit = Column(String(32))
    rate = Column(Float)
    taxable_value = Column(Float)
    gst_percent = Column(Float, default=18)
    gst_amount = Column(Float)
    invoice_total = Column(Float)
    payment_status = Column(String(32))

    supplier = relationship("Supplier")
    material = relationship("Material")

class Issue(Base):
    __tablename__ = "issues"
    id = Column(Integer, primary_key=True)
    issue_no = Column(String(64), unique=True)
    date = Column(Date)
    project_id = Column(String(64))
    client_project = Column(String(256))
    material_id = Column(Integer, ForeignKey("materials.id"))
    quantity_issued = Column(Float)
    unit = Column(String(32))
    issued_to = Column(String(128))
    department = Column(String(128))
    purpose = Column(String(256))
    approved_by = Column(String(128))
    remarks = Column(Text)

    material = relationship("Material")

class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True)
    client_id = Column(String(32), unique=True)
    name = Column(String(256))
    phone = Column(String(64))
    email = Column(String(256))
    address = Column(Text)
    lead_source = Column(String(128))
    first_contact_date = Column(Date)
    remarks = Column(Text)
