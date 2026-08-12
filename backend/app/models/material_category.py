from sqlalchemy import Column, String, Integer, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class MaterialCategory(BaseModel):
    """Top level of the material hierarchy - e.g. "Board & Wood
    Materials". Never hard-coded: users create their own categories:
    Category -> Subcategory -> Material (-> dynamic attributes)."""
    __tablename__ = "material_categories"

    business_id = Column(String(10), unique=True, index=True, nullable=True)
    name = Column(String(150), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)

    subcategories = relationship("MaterialSubcategory", back_populates="category",
                                  cascade="all, delete-orphan", order_by="MaterialSubcategory.name")


class MaterialSubcategory(BaseModel):
    """Second level - e.g. "Plywood", "HDHMR" under "Board & Wood
    Materials". This is what a Material's specifications and dynamic
    attribute set are actually defined against (thickness/sheet size
    for Plywood vs voltage/wattage for LED Strip), per the product
    principle that different material types need different attributes."""
    __tablename__ = "material_subcategories"
    __table_args__ = (UniqueConstraint("category_id", "name", name="uq_subcategory_per_category"),)

    business_id = Column(String(10), unique=True, index=True, nullable=True)
    category_id = Column(Integer, ForeignKey("material_categories.id"), nullable=False, index=True)
    name = Column(String(150), nullable=False, index=True)
    description = Column(Text, nullable=True)

    category = relationship("MaterialCategory", back_populates="subcategories")
    attribute_definitions = relationship("MaterialAttributeDefinition", back_populates="subcategory",
                                          cascade="all, delete-orphan",
                                          order_by="MaterialAttributeDefinition.sort_order")
    materials = relationship("Material", back_populates="subcategory")
