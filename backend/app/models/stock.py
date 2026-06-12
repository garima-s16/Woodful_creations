"""
Stock module database models - Enhanced with material types and variants
Defines the structure for product inventory management with specific materials
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, Enum, ForeignKey
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


class MaterialType(str, enum.Enum):
    """Enum for material types"""
    PLYWOOD_COMMERCIAL = "plywood_commercial"
    BWP_PLYWOOD = "bwp_plywood"
    MARINE_PLYWOOD = "marine_plywood"
    MDF = "mdf"
    PRELAMINATED_MDF = "prelaminated_mdf"
    HDHMR = "hdhmr"
    HDF = "hdf"
    PARTICLE_BOARD = "particle_board"
    PRELAMINATED_PARTICLE = "prelaminated_particle"
    BLOCK_BOARD = "block_board"
    FLUSH_DOOR_BOARD = "flush_door_board"
    WPC_BOARD = "wpc_board"
    PVC_BOARD = "pvc_board"
    ACRYLIC_SHEET = "acrylic_sheet"
    VENEER_MDF_PLYWOOD = "veneer_mdf_plywood"
    FLEXI_PLYWOOD = "flexi_plywood"


# Material type to thicknesses mapping
MATERIAL_THICKNESSES = {
    MaterialType.PLYWOOD_COMMERCIAL: [6, 12, 18],
    MaterialType.BWP_PLYWOOD: [6, 12, 18],
    MaterialType.MARINE_PLYWOOD: [6, 12, 18],
    MaterialType.MDF: [3, 6, 12, 18],
    MaterialType.PRELAMINATED_MDF: [6, 12, 18],
    MaterialType.HDHMR: [6, 12, 18],
    MaterialType.HDF: [2.5, 3, 4],
    MaterialType.PARTICLE_BOARD: [12, 18],
    MaterialType.PRELAMINATED_PARTICLE: [18],
    MaterialType.BLOCK_BOARD: [19, 25],
    MaterialType.FLUSH_DOOR_BOARD: [30, 35],
    MaterialType.WPC_BOARD: [6, 12, 18],
    MaterialType.PVC_BOARD: [6, 12, 18],
    MaterialType.ACRYLIC_SHEET: [3, 5, 8],
    MaterialType.VENEER_MDF_PLYWOOD: [6, 12, 18],
    MaterialType.FLEXI_PLYWOOD: [6, 8],
}


class StockCategory(Base):
    """Stock category model"""
    __tablename__ = "stock_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Product(Base):
    """Product model for materials"""
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)  # e.g., "Plywood (Commercial/MR)"
    sku_prefix = Column(String(50), unique=True, index=True, nullable=False)  # e.g., "PLY-COM"
    description = Column(Text, nullable=True)
    category_id = Column(Integer, index=True, nullable=False)
    
    # Material classification
    material_type = Column(Enum(MaterialType), index=True, nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProductVariant(Base):
    """Product variant model for different thicknesses/sizes"""
    __tablename__ = "product_variants"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), index=True, nullable=False)
    
    # Variant specifications
    thickness = Column(Float, nullable=False)  # in mm
    unit = Column(String(50), default="sheet")  # sheet, pcs, etc.
    
    # SKU for this variant
    sku = Column(String(100), unique=True, index=True, nullable=False)  # e.g., "PLY-COM-006" for 6mm
    barcode = Column(String(100), unique=True, nullable=True)
    
    # Stock information
    quantity_in_stock = Column(Integer, default=0)
    minimum_quantity = Column(Integer, default=10)
    reorder_quantity = Column(Integer, default=50)
    status = Column(Enum(StockStatus), default=StockStatus.IN_STOCK, index=True)
    
    # Standard dimensions (optional)
    standard_width = Column(Float, nullable=True)  # Default sheet width in inches/cm
    standard_length = Column(Float, nullable=True)  # Default sheet length
    standard_area = Column(Float, nullable=True)   # Calculated area per unit
    
    # Pricing
    cost_price = Column(Float, nullable=False)  # Per sheet/unit
    selling_price = Column(Float, nullable=False)
    
    # Supplier information
    supplier_id = Column(Integer, nullable=True)
    supplier_name = Column(String(255), nullable=True)
    
    # Grade/Quality
    grade = Column(String(100), nullable=True)  # For materials like "Grade A", "Commercial"
    finish = Column(String(100), nullable=True)  # For laminates like "Glossy", "Matte"
    
    # Storage
    location = Column(String(255), nullable=True)  # Storage location/shelf
    is_active = Column(Boolean, default=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_restocked = Column(DateTime, nullable=True)


class StockMovement(Base):
    """Stock movement/transaction history model"""
    __tablename__ = "stock_movements"
    
    id = Column(Integer, primary_key=True, index=True)
    variant_id = Column(Integer, ForeignKey("product_variants.id"), index=True, nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), index=True, nullable=False)
    
    # Movement details
    movement_type = Column(String(50), index=True, nullable=False)  # in, out, adjustment, return
    quantity = Column(Integer, nullable=False)
    reason = Column(String(255), nullable=True)  # Restock, Sale, Damage, Return, Wastage, etc.
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
    variant_id = Column(Integer, ForeignKey("product_variants.id"), index=True, nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), index=True, nullable=False)
    
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
    variant_id = Column(Integer, ForeignKey("product_variants.id"), index=True, nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), index=True, nullable=False)
    
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
