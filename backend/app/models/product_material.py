from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class ProductMaterial(BaseModel):
    """A real bill-of-materials line: how much of a given Material one
    unit of a Product consumes. This is what makes "materials" on the
    Product Master a genuine relational fact (queryable, reusable for
    a future costing/shortage calculation) rather than a free-text
    field a person has to re-type and keep in sync by hand - the same
    principle SupplierMaterial already established for
    Supplier<->Material pricing."""
    __tablename__ = "product_materials"
    __table_args__ = (UniqueConstraint("product_id", "material_id", name="uq_product_material"),)

    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)
    quantity = Column(Numeric(10, 2), nullable=False, default=1)
    unit = Column(String(20), nullable=True)  # defaults to the material's own unit if not supplied

    product = relationship("Product", back_populates="bom_items")
    material = relationship("Material")
