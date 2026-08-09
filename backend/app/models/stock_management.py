from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    contact_person = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    materials = relationship("Material", back_populates="supplier")


class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    category = Column(String(255), nullable=False, index=True)
    unit = Column(String(50), default="unit", nullable=False)
    opening_stock = Column(Float, default=0.0, nullable=False)
    minimum_stock = Column(Float, default=0.0, nullable=False)
    unit_price = Column(Float, default=0.0, nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    supplier = relationship("Supplier", back_populates="materials")
    stock_ins = relationship("StockIn", back_populates="material", cascade="all, delete-orphan")
    stock_outs = relationship("StockOut", back_populates="material", cascade="all, delete-orphan")


class StockIn(Base):
    __tablename__ = "stock_ins"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=True)
    invoice_number = Column(String(100), nullable=True)
    purchased_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    notes = Column(Text, nullable=True)

    material = relationship("Material", back_populates="stock_ins")


class StockOut(Base):
    __tablename__ = "stock_outs"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    issued_to = Column(String(255), nullable=True)
    issued_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    notes = Column(Text, nullable=True)

    material = relationship("Material", back_populates="stock_outs")


class AppSetting(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(255), default="Woodful Creations", nullable=False)
    currency = Column(String(10), default="INR", nullable=False)
    reorder_buffer = Column(Float, default=1.2, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
