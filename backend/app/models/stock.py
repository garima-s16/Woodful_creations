"""
Stock module database models
Defines the structure for product inventory management
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, Enum
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()


class StockStatus(str, enum.Enum):
    """Enum for stock status"""
    IN_STOCK = "in_stock"
    LOW_STOCK = "low_stock"
    OUT_OF_STOCK = "out_of_stock"
    DISCONTINUED = "discontinued"
    UNDER_REVIEW = "under_review"


class StockCategory(Base):
    """Stock category model"""
    __tablename__ = "stock_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Product(Base):
    """Product model"""
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    sku = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    category_id = Column(Integer, index=True, nullable=False)
    
    # Stock information
    quantity_in_stock = Column(Integer, default=0)
    minimum_quantity = Column(Integer, default=10)
    reorder_quantity = Column(Integer, default=50)
    status = Column(Enum(StockStatus), default=StockStatus.IN_STOCK, index=True)
    
    # Pricing
    cost_price = Column(Float, nullable=False)
    selling_price = Column(Float, nullable=False)
    
    # Details
    supplier_id = Column(Integer, nullable=True)
    location = Column(String(255), nullable=True)
    barcode = Column(String(100), unique=True, nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_restocked = Column(DateTime, nullable=True)


class StockMovement(Base):
    """Stock movement/transaction history model"""
    __tablename__ = "stock_movements"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, index=True, nullable=False)
    
    # Movement details
    movement_type = Column(String(50), index=True, nullable=False)  # in, out, adjustment
    quantity = Column(Integer, nullable=False)
    reason = Column(String(255), nullable=True)  # Restock, Sale, Damage, etc.
    reference_number = Column(String(100), nullable=True)  # PO, Invoice, etc.
    
    # User information
    updated_by = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class StockAlert(Base):
    """Stock alert model for low stock notifications"""
    __tablename__ = "stock_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, index=True, nullable=False)
    
    # Alert details
    alert_type = Column(String(50), nullable=False)  # low_stock, out_of_stock, overstock
    threshold = Column(Integer, nullable=False)
    current_quantity = Column(Integer, nullable=False)
    
    # Alert status
    is_active = Column(Boolean, default=True)
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    
    # Notification
    notified_users = Column(String(500), nullable=True)  # Comma-separated user IDs
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class InventoryAudit(Base):
    """Inventory audit log model"""
    __tablename__ = "inventory_audits"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, index=True, nullable=False)
    
    # Audit details
    system_quantity = Column(Integer, nullable=False)
    physical_quantity = Column(Integer, nullable=False)
    variance = Column(Integer, nullable=False)
    variance_percentage = Column(Float, nullable=False)
    
    # Audit info
    audited_by = Column(String(255), nullable=False)
    notes = Column(Text, nullable=True)
    action_taken = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
