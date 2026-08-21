from sqlalchemy import Column, String, Integer, Numeric, Boolean, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Product(BaseModel):
    """Product Master - what Woodful actually sells: standard catalog
    pieces (product_type="standard") and one-off custom furniture
    (product_type="custom"), in one table rather than two, since an
    order/estimate item needs to point at either kind the same way.

    Reference images and attachments (drawings, spec sheets) reuse the
    existing GenericDocument infrastructure (parent_type="product") -
    see app/models/generic_document.py - rather than a dedicated table,
    the same way order/supplier/purchase/employee documents already work.
    """
    __tablename__ = "products"

    product_code = Column(String(20), unique=True, nullable=False, index=True)  # PRD-001, human-scannable reference
    # Centralized, incremental, system-generated 10-character external ID -
    # see app/utils/id_generator.generate_business_id. Never client-supplied.
    business_id = Column(String(10), unique=True, index=True, nullable=False)

    name = Column(String(255), nullable=False, index=True)
    # "standard" = catalog product, ordered as-is, repeatable.
    # "custom" = one-off furniture built to a specific client's brief -
    # still gets a Product Master row (so it appears in order items and
    # costing/reporting like anything else), just flagged distinctly and
    # typically created from an estimate/order rather than pre-catalogued.
    product_type = Column(String(20), nullable=False, default="standard", index=True)

    category = Column(String(100), nullable=True, index=True)
    subcategory = Column(String(100), nullable=True, index=True)
    specifications = Column(Text, nullable=True)

    length = Column(Numeric(10, 2), nullable=True)
    width = Column(Numeric(10, 2), nullable=True)
    height = Column(Numeric(10, 2), nullable=True)
    dimension_unit = Column(String(10), nullable=True, default="in")

    primary_material = Column(String(150), nullable=True)  # free-text summary, e.g. "BWP Plywood + Teak veneer"
    finish = Column(String(150), nullable=True)
    unit = Column(String(20), nullable=False, default="Nos")
    # Default GST % - a reference value only, used to pre-fill a new
    # Estimate/Order line item's rate defaults are separate; this is
    # purely a suggestion. Changing it later must never alter any
    # historical Estimate/Order, which already store their own
    # tax_percent independently (see app/utils/calculations.py).
    gst_percent = Column(Numeric(5, 2), nullable=True, default=18)

    # Costing breakdown - a real production cost estimate, itemized by
    # component, rather than one opaque number. cost_price (below) is
    # the sum of these plus overhead; keeping the breakdown lets a
    # product's cost actually be explained/audited, not just quoted.
    material_cost = Column(Numeric(12, 2), nullable=True)
    hardware_cost = Column(Numeric(12, 2), nullable=True)
    labour_cost = Column(Numeric(12, 2), nullable=True)
    machine_cost = Column(Numeric(12, 2), nullable=True)
    finish_cost = Column(Numeric(12, 2), nullable=True)
    packing_cost = Column(Numeric(12, 2), nullable=True)
    transport_cost = Column(Numeric(12, 2), nullable=True)
    other_cost = Column(Numeric(12, 2), nullable=True)
    overhead_percent = Column(Numeric(5, 2), nullable=True)  # applied on top of the summed cost components
    margin_percent = Column(Numeric(5, 2), nullable=True)  # the target margin used to derive selling_price

    # cost_price/selling_price stay as real stored, editable fields -
    # a product's actual list price is a business decision, not always
    # exactly what the formula below suggests (a catalog price might be
    # rounded, negotiated, or held steady across a raw-material blip).
    # suggested_cost_price/suggested_selling_price (below) show what the
    # breakdown implies, for comparison.
    cost_price = Column(Numeric(12, 2), nullable=True)  # material + labor cost to produce
    selling_price = Column(Numeric(12, 2), nullable=True)  # standard list price

    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    order_items = relationship("OrderItem", back_populates="product")
    estimate_line_items = relationship("EstimateLineItem", back_populates="product")
    materials_used = relationship("ProductMaterial", back_populates="product", cascade="all, delete-orphan")

    @property
    def suggested_cost_price(self):
        """Sum of the itemized cost components plus overhead_percent -
        what the breakdown implies the product should cost to produce,
        for comparison against the stored cost_price (which a human may
        have overridden). None if no cost components were entered at
        all, rather than treating unset fields as zero."""
        components = [
            self.material_cost, self.hardware_cost, self.labour_cost, self.machine_cost,
            self.finish_cost, self.packing_cost, self.transport_cost, self.other_cost,
        ]
        provided = [c for c in components if c is not None]
        if not provided:
            return None
        base = sum(float(c) for c in provided)
        if self.overhead_percent:
            base += base * float(self.overhead_percent) / 100
        return round(base, 2)

    @property
    def suggested_selling_price(self):
        """Uses the SAME formula as app/utils/pricing_engine.compute_selling_rate
        (Selling Price = Cost / (1 - Margin%)) - not duplicated here,
        called directly, so this can never silently drift from the one
        authoritative calculation. This was previously a markup formula
        (base * (1 + margin%)), which understates the selling price for
        any given margin% - Cost 100 at 30% margin must be 142.86, not 130."""
        base = self.suggested_cost_price
        if base is None or not self.margin_percent:
            return None
        from decimal import Decimal
        from app.utils.pricing_engine import compute_selling_rate
        return float(compute_selling_rate(Decimal(str(base)), Decimal(str(self.margin_percent))))

    @property
    def margin(self):
        if self.cost_price is None or self.selling_price is None:
            return None
        return round(float(self.selling_price) - float(self.cost_price), 2)

    @property
    def actual_margin_percent(self):
        """The real margin %, computed from the stored cost_price/
        selling_price - distinct from the margin_percent *column*
        above, which is the target margin used to derive a suggested
        selling_price. The two can differ (e.g. a negotiated discount
        brought the actual margin below target)."""
        if not self.cost_price or self.selling_price is None:
            return None
        cost = float(self.cost_price)
        if cost <= 0:
            return None
        return round((float(self.selling_price) - cost) / cost * 100, 2)


class ProductMaterial(BaseModel):
    """Bill-of-materials line: which raw Materials a Product consumes,
    and how much of each - the real link between the Product Master and
    the existing Material Stock Master, so a product's material cost can
    be derived from real stock data rather than only the flat
    Product.cost_price estimate."""
    __tablename__ = "product_materials"
    __table_args__ = (UniqueConstraint("product_id", "material_id", name="uq_product_material_pair"),)

    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)
    quantity_required = Column(Numeric(10, 2), nullable=False, default=1)
    unit = Column(String(20), nullable=True)
    notes = Column(String(255), nullable=True)

    product = relationship("Product", back_populates="materials_used")
    material = relationship("Material")

    @property
    def material_name(self):
        return self.material.name if self.material else None
