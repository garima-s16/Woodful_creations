"""Inventory models"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Numeric, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database import Base

class MovementType(str, enum.Enum):
    """Stock movement type"""
    IN = "in"
    OUT = "out"
    ADJUSTMENT = "adjustment"

class AlertType(str, enum.Enum):
    """Stock alert type"""
    LOW_STOCK = "low_stock"
    OUT_OF_STOCK = "out_of_stock"
    OVERSTOCK = "overstock"

class InventoryCategory(Base):
    """Inventory category model"""
    __tablename__ = "inventory_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    deletion_status = Column(String(20), default="active")
    
    # Relationships
    items = relationship("InventoryItem", back_populates="category")
    
    class Config:
        from_attributes = True

class InventoryItem(Base):
    """Inventory item model"""
    __tablename__ = "inventory_items"
    
    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(50), unique=True, nullable=False, index=True)
    product_name = Column(String(255), nullable=False)
    category_id = Column(Integer, ForeignKey("inventory_categories.id"), nullable=True)
    description = Column(Text, nullable=True)
    quantity = Column(Integer, default=0, nullable=False)
    minimum_stock = Column(Integer, default=10)
    reorder_quantity = Column(Integer, default=50)
    unit_cost = Column(Numeric(12, 2), nullable=True)
    selling_price = Column(Numeric(12, 2), nullable=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    warehouse_location = Column(String(100), nullable=True)
    image_url = Column(String(500), nullable=True)
    barcode = Column(String(100), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deletion_status = Column(String(20), default="active")
    
    # Relationships
    category = relationship("InventoryCategory", back_populates="items")
    movements = relationship("StockMovement", back_populates="item", cascade="all, delete-orphan")
    alerts = relationship("StockAlert", back_populates="item", cascade="all, delete-orphan")
    
    class Config:
        from_attributes = True

class StockMovement(Base):
    """Stock movement history model"""
    __tablename__ = "stock_movements"
    
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False, index=True)
    movement_type = Column(SQLEnum(MovementType), nullable=False)
    quantity = Column(Integer, nullable=False)
    reason = Column(String(255), nullable=True)
    reference_id = Column(Integer, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    item = relationship("InventoryItem", back_populates="movements")
    
    class Config:
        from_attributes = True

class StockAlert(Base):
    """Stock alert model"""
    __tablename__ = "stock_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_type = Column(SQLEnum(AlertType), nullable=False)
    quantity = Column(Integer, nullable=True)
    alert_triggered_at = Column(DateTime, default=datetime.utcnow)
    acknowledged_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    deletion_status = Column(String(20), default="active")
    
    # Relationships
    item = relationship("InventoryItem", back_populates="alerts")
    
    class Config:
        from_attributes = True

class Supplier(Base):
    """Supplier model"""
    __tablename__ = "suppliers"
    
    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(255), nullable=False, index=True)
    contact_person = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    postal_code = Column(String(20), nullable=True)
    payment_terms = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    deletion_status = Column(String(20), default="active")
    
    class Config:
        from_attributes = True
