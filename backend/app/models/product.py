from sqlalchemy import Column, String, Integer, Numeric, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

# Kept intentionally small and explicit, matching the standing project
# principle (see Material/Estimate line items) against free-typed status
# strings for anything an API consumer branches on.
PRODUCT_TYPES = ["standard", "custom"]


class Product(BaseModel):
    """Product Master (Family 21) - the real catalog of what Woodful
    actually sells/builds: standard catalog items ("Sliding Wardrobe -
    3 Door") as well as one-off custom furniture pieces made for a
    single client, both represented the same way so an OrderItem/
    EstimateLineItem can point at either kind through one relationship.

    product_code is the human-scannable sequential reference
    (PROD-001, server-generated, same discipline as every other *_code
    column in this app). business_id is the centralized, atomic,
    incremental 10-character global ID (see utils/id_generator.py).
    Neither is ever accepted from client input.

    Costing: cost_price is what it costs Woodful to make/source this
    (material + labor estimate); selling_price is what a client is
    quoted. Both are genuinely financial figures and are redacted for
    non-master roles in the API response, same pattern as
    Material.average_rate/stock_value - see _serialize_products() in
    api/routes/products.py."""
    __tablename__ = "products"

    product_code = Column(String(20), unique=True, nullable=False, index=True)  # PROD-001
    business_id = Column(String(10), unique=True, index=True, nullable=True)
    sku = Column(String(50), unique=True, nullable=True, index=True)

    name = Column(String(255), nullable=False, index=True)
    product_type = Column(String(20), nullable=False, default="standard", index=True)  # standard | custom

    # Kept for backward compatibility with the same sync pattern as
    # Material.category/Material.location - when subcategory_id is set,
    # this is server-synced from the subcategory's parent category name
    # (see _resolve_product_category_name() in api/routes/products.py),
    # so anything that ever reads this flat string directly stays correct.
    category = Column(String(100), nullable=True, index=True)
    subcategory_id = Column(Integer, ForeignKey("product_subcategories.id"), nullable=True, index=True)

    description = Column(Text, nullable=True)
    specifications = Column(Text, nullable=True)  # free-text spec sheet (materials/construction notes, etc.)

    # Dimensions - a real furniture business quotes/plans against actual
    # size, not just a name. Numeric (not Integer) since furniture is
    # routinely specified to a fraction of an inch/cm.
    length = Column(Numeric(10, 2), nullable=True)
    width = Column(Numeric(10, 2), nullable=True)
    height = Column(Numeric(10, 2), nullable=True)
    dimension_unit = Column(String(10), nullable=False, default="in")  # in | cm | ft | mm

    finish = Column(String(150), nullable=True)  # e.g. "Matte Laminate", "PU Painted", "Natural Wood"
    unit = Column(String(20), nullable=False, default="Piece")

    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    cost_price = Column(Numeric(12, 2), nullable=False, default=0)
    selling_price = Column(Numeric(12, 2), nullable=False, default=0)
    tax_percent = Column(Numeric(5, 2), nullable=False, default=18)
    lead_time_days = Column(Integer, nullable=True)

    subcategory = relationship("ProductSubcategory", back_populates="products")
    bom_items = relationship("ProductMaterial", back_populates="product", cascade="all, delete-orphan")
    order_items = relationship("OrderItem", back_populates="product")
    estimate_line_items = relationship("EstimateLineItem", back_populates="product")

    @property
    def margin(self):
        """Selling price minus cost price - None (not 0) when either
        figure is genuinely absent, so the frontend can tell "not priced
        yet" apart from a real zero margin."""
        if self.selling_price is None or self.cost_price is None:
            return None
        return round(float(self.selling_price) - float(self.cost_price), 2)
