from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Material(BaseModel):
    """Live Material Stock Master. current_stock/total_purchased/total_issued
    are maintained transactionally by StockService whenever a Purchase or
    Issue is recorded - see services/stock_service.py."""
    __tablename__ = "materials"

    material_code = Column(String(20), unique=True, nullable=False, index=True)  # MAT-001
    # Opaque 10-char external identifier (e.g. A7K92P4XQ1) - separate from
    # material_code, which stays as the human-scannable sequential reference.
    business_id = Column(String(10), unique=True, index=True, nullable=True)
    name = Column(String(255), nullable=False, index=True)
    # Kept for backward compatibility - every existing consumer (dashboard,
    # chatbot, PDF, Excel, purchases, issues) reads this directly. New
    # material creation should set subcategory_id instead; category stays
    # in sync (subcategory's own category name) so nothing reading this
    # column directly goes stale - see MaterialService.
    category = Column(String(100), nullable=True, index=True)
    subcategory_id = Column(Integer, ForeignKey("material_subcategories.id"), nullable=True, index=True)
    brand_grade = Column(String(100), nullable=True)
    thickness_size = Column(String(50), nullable=True)
    unit = Column(String(20), nullable=False)

    opening_stock = Column(Integer, nullable=False, default=0)
    total_purchased = Column(Integer, nullable=False, default=0)
    total_issued = Column(Integer, nullable=False, default=0)
    current_stock = Column(Integer, nullable=False, default=0, index=True)
    minimum_stock = Column(Integer, nullable=False, default=0)

    average_rate = Column(Numeric(12, 2), nullable=False, default=0)

    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True, index=True)
    # Kept for backward compatibility - existing consumers read this
    # directly. When location_id is set, this is derived server-side
    # from the Location's full_path, not taken from client input.
    location = Column(String(100), nullable=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True, index=True)

    primary_supplier = relationship("Supplier", back_populates="materials")
    purchases = relationship("Purchase", back_populates="material")
    issues = relationship("Issue", back_populates="material")
    subcategory = relationship("MaterialSubcategory", back_populates="materials")
    attribute_values = relationship("MaterialAttributeValue", back_populates="material",
                                     cascade="all, delete-orphan")
    supplier_materials = relationship("SupplierMaterial", back_populates="material", cascade="all, delete-orphan")
    location_ref = relationship("Location")

    @property
    def stock_value(self):
        return round(float(self.current_stock or 0) * float(self.average_rate or 0), 2)

    @property
    def stock_status(self):
        if (self.current_stock or 0) <= 0:
            return "OUT OF STOCK"
        if (self.current_stock or 0) <= (self.minimum_stock or 0):
            return "LOW STOCK"
        return "STOCK OK"
