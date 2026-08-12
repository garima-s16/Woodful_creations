from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, Boolean, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class SupplierMaterial(BaseModel):
    """The real many-to-many: a supplier can supply many materials, a
    material can have many suppliers, each with its own pricing/terms.
    Distinct from Material.supplier_id (the single "primary supplier"
    field, kept for backward compatibility with existing purchases/
    dashboard code) - this table is where genuine multi-supplier
    comparison data lives."""
    __tablename__ = "supplier_materials"
    __table_args__ = (UniqueConstraint("supplier_id", "material_id", name="uq_supplier_material_pair"),)

    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)
    supplier_sku = Column(String(100), nullable=True)  # the supplier's own code for this material
    supplier_price = Column(Numeric(12, 2), nullable=True)  # current quoted/listed price
    # Updated automatically whenever a Purchase is recorded against this
    # exact supplier+material pair (see StockService.record_purchase) -
    # not something the user has to remember to update by hand.
    last_purchase_price = Column(Numeric(12, 2), nullable=True)
    moq = Column(Integer, nullable=True)  # minimum order quantity
    lead_time_days = Column(Integer, nullable=True)
    is_preferred = Column(Boolean, nullable=False, default=False)
    notes = Column(Text, nullable=True)

    supplier = relationship("Supplier", back_populates="supplier_materials")
    material = relationship("Material", back_populates="supplier_materials")

    @property
    def supplier_name(self):
        return self.supplier.name if self.supplier else None

    @property
    def material_name(self):
        return self.material.name if self.material else None
