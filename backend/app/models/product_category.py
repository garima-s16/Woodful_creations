from sqlalchemy import Column, String, Integer, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class ProductCategory(BaseModel):
    """Top level of the Product Master hierarchy - e.g. "Bedroom
    Furniture", "Modular Kitchen", "Seating". Mirrors the
    MaterialCategory/MaterialSubcategory pattern deliberately (Family 21
    was told not to copy the old spreadsheet architecture, but *this*
    hierarchy shape - Category -> Subcategory -> real records - is
    already a proven, tested pattern in this codebase and there's no
    reason to invent a second one for finished-goods products. Kept as
    an entirely separate table from MaterialCategory though: a product
    ("Wardrobe") and a material ("HDHMR 18mm") are fundamentally
    different kinds of thing and must never share a category list."""
    __tablename__ = "product_categories"

    business_id = Column(String(10), unique=True, index=True, nullable=True)
    name = Column(String(150), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)

    subcategories = relationship("ProductSubcategory", back_populates="category",
                                  cascade="all, delete-orphan", order_by="ProductSubcategory.name")


class ProductSubcategory(BaseModel):
    """Second level - e.g. "Wardrobes", "Beds" under "Bedroom
    Furniture". What a Product's category filter is actually defined
    against."""
    __tablename__ = "product_subcategories"
    __table_args__ = (UniqueConstraint("category_id", "name", name="uq_product_subcategory_per_category"),)

    business_id = Column(String(10), unique=True, index=True, nullable=True)
    category_id = Column(Integer, ForeignKey("product_categories.id"), nullable=False, index=True)
    name = Column(String(150), nullable=False, index=True)
    description = Column(Text, nullable=True)

    category = relationship("ProductCategory", back_populates="subcategories")
    products = relationship("Product", back_populates="subcategory")
