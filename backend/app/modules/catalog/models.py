"""Catalog/pricing domain models: Product, ProductMaterial, RateCard,
plus the RateCard controlled-vocabulary constants and UOM validation
helper.

Consolidated from product.py + rate_card.py.
"""
from sqlalchemy import Column, String, Integer, Numeric, Boolean, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.platform.database.base import BaseModel


class Product(BaseModel):
    """Product Master - what Woodful actually sells: standard catalog
    pieces (product_type="standard") and one-off custom furniture
    (product_type="custom"), in one table rather than two, since an
    order/estimate item needs to point at either kind the same way.

    Reference images and attachments (drawings, spec sheets) reuse the
    existing GenericDocument infrastructure (parent_type="product") -
    see app/modules/documents/models.py - rather than a dedicated table,
    the same way order/supplier/purchase/employee documents already work.
    """
    __tablename__ = "products"

    product_code = Column(String(20), unique=True, nullable=False, index=True)  # PRD-001, human-scannable reference
    # Centralized, incremental, system-generated 10-character external ID -
    # see app/platform/database/id_generator.generate_business_id. Never client-supplied.
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
    # tax_percent independently (see app/modules/sales/calculations.py).
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
        """Uses the SAME formula as app/modules/catalog/pricing_engine.compute_selling_rate
        (Selling Price = Cost / (1 - Margin%)) - not duplicated here,
        called directly, so this can never silently drift from the one
        authoritative calculation. This was previously a markup formula
        (base * (1 + margin%)), which understates the selling price for
        any given margin% - Cost 100 at 30% margin must be 142.86, not 130."""
        base = self.suggested_cost_price
        if base is None or not self.margin_percent:
            return None
        from decimal import Decimal
        from app.modules.catalog.pricing_engine import compute_selling_rate
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


# Controlled vocabularies - not free text, so a report grouping by
# source_type/confidence actually groups consistently (Rate
# Versioning section: every rate needs these as first-class fields).
RATE_SOURCE_TYPES = {
    "INDORE_SUPPLIER", "INDORE_SERVICE_PROVIDER", "INDORE_MARKET_LISTING",
    "NATIONAL_MARKET_BENCHMARK", "WOODFUL_HISTORICAL", "WOODFUL_INTERNAL", "MANUAL_VERIFIED",
}
RATE_CONFIDENCE_LEVELS = {"HIGH", "MEDIUM", "LOW", "NOT_VERIFIED"}

# Market-standard UOMs only - "Standard UOM Rule": do not let every unit
# apply to every item type (no "Furniture -> Litre").
STANDARD_UOMS = {
    "Piece", "Set", "Pair", "Sq Ft", "Running Ft", "Meter", "Sq Meter", "Kg", "Gram",
    "Litre", "Millilitre", "Sheet", "Box", "Pack", "Roll", "Bundle", "Cu Ft",
    "Minute", "Hour", "Day", "Job", "Hole",
}

# Category -> the subset of STANDARD_UOMS actually sensible for it -
# this is what makes "Furniture -> Litre" a rejected combination
# rather than merely "Litre isn't a real unit" (it is, just not for
# furniture). Categories not listed here have no restriction beyond
# STANDARD_UOMS itself (e.g. a catch-all "Other" category).
#
# Furniture allows Sq Ft/Running Ft alongside Piece/Set/Pair - modular
# furniture (wardrobes, kitchen cabinets, full-height storage) is
# genuinely priced by area in real Woodful/market data (Dimension
# Pricing section: "Where an existing product is configured for
# area-based pricing... Do not force every furniture product into area
# pricing" - the point is BOTH bases are legitimate depending on the
# item, not that Piece is the only valid one).
CATEGORY_UOM_RULES = {
    "Furniture": {"Piece", "Set", "Pair", "Sq Ft", "Running Ft"},
    "Material": {"Sq Ft", "Running Ft", "Sheet", "Kg", "Gram", "Meter", "Sq Meter", "Litre", "Millilitre", "Box", "Roll", "Bundle", "Piece", "Cu Ft"},
    "Hardware": {"Piece", "Set", "Pair", "Box", "Pack"},
    "Labour": {"Hour", "Day", "Job", "Sq Ft", "Piece"},
    "Machine": {"Minute", "Hour", "Job", "Sq Ft", "Hole"},
    "Finishing": {"Sq Ft", "Litre", "Millilitre", "Kg", "Job", "Running Ft"},
    "Installation": {"Piece", "Job", "Day", "Hour"},  # billed as Job/Day/Hour, not a separate "Trip" unit
    "Transport": {"Job", "Day", "Piece"},
    # "Service" is a legitimate rollup spanning machine-time (Minute),
    # labour (Hour), area-based finishing (Sq Ft), and job-based
    # installation all under one umbrella - confirmed by real supplied
    # market data mixing all four bases under this one category. Union
    # of what Machine/Labour/Finishing/Installation each allow, rather
    # than one narrow basis.
    "Service": {"Minute", "Hour", "Day", "Job", "Sq Ft", "Piece"},
}


def uom_allowed_for_category(category: str, uom: str) -> bool:
    """True if uom is a real STANDARD_UOM at all AND (the category has
    no specific restriction, or uom is in that category's allowed
    subset). Unknown/unlisted categories fall back to "any standard
    UOM is fine" rather than blocking legitimate new categories."""
    if uom not in STANDARD_UOMS:
        return False
    allowed = CATEGORY_UOM_RULES.get(category)
    return allowed is None or uom in allowed


class RateCard(BaseModel):
    """One versioned rate entry across the three pricing layers -
    Indore Market Reference, Woodful Internal Cost, Woodful Selling
    Rate - for a Category -> Subcategory -> Product/Service ->
    Specification. Never overwritten: a rate change creates a new
    RateCard row with a new effective_from and deactivates the
    previous one (see app/modules/catalog/api/rate_cards.py), so any Estimate/
    Order that already snapshotted a rate_card_id keeps pointing at
    the exact historical rate it used, even after prices change.
    """
    __tablename__ = "rate_cards"

    rate_code = Column(String(20), unique=True, nullable=False, index=True)  # RATE-001
    business_id = Column(String(10), unique=True, index=True, nullable=False)

    category = Column(String(100), nullable=False, index=True)
    subcategory = Column(String(100), nullable=True, index=True)
    item_name = Column(String(255), nullable=False, index=True)  # Product/Service
    specification = Column(String(255), nullable=True)  # grade/brand/thickness/variant - e.g. "18mm BWP"
    location = Column(String(100), nullable=False, default="Indore, Madhya Pradesh")
    uom = Column(String(20), nullable=False)  # must be one of STANDARD_UOMS - validated in the schema

    # THREE LAYERS - deliberately separate columns, never merged into
    # one "rate" field, per the spec's central "do not confuse market
    # price with cost with selling price" rule.
    market_reference_rate = Column(Numeric(12, 2), nullable=True)
    woodful_cost_rate = Column(Numeric(12, 2), nullable=True)
    woodful_selling_rate = Column(Numeric(12, 2), nullable=True)

    # Cost-engine inputs, kept alongside the resulting woodful_cost_rate/
    # woodful_selling_rate so the calculation is auditable, not just the
    # final numbers - see app/modules/catalog/pricing_engine.py, the one place
    # that turns these into the two rates above.
    overhead_percent = Column(Numeric(5, 2), nullable=True)
    target_margin_percent = Column(Numeric(5, 2), nullable=True)
    wastage_percent = Column(Numeric(5, 2), nullable=True)
    tax_percent = Column(Numeric(5, 2), nullable=True, default=18)

    effective_from = Column(DateTime, nullable=False)
    effective_to = Column(DateTime, nullable=True)  # null = still current
    is_active = Column(Boolean, nullable=False, default=True)

    source_type = Column(String(40), nullable=False)  # one of RATE_SOURCE_TYPES
    source_reference = Column(String(500), nullable=True)  # URL/supplier name/citation
    confidence = Column(String(20), nullable=False, default="NOT_VERIFIED")  # one of RATE_CONFIDENCE_LEVELS
    notes = Column(Text, nullable=True)

    # Versioning chain: a new rate for the same item points back at
    # what it superseded, so "Rate History" can walk the chain without
    # relying on fuzzy category/item_name matching.
    supersedes_id = Column(Integer, ForeignKey("rate_cards.id"), nullable=True)

    # Manual override tracking (spec's "Manual Override" section):
    # who overrode the calculated selling rate, when, and why - never a
    # silent overwrite of the calculated figure.
    override_price = Column(Numeric(12, 2), nullable=True)
    override_by = Column(String(255), nullable=True)
    override_at = Column(DateTime, nullable=True)
    override_reason = Column(Text, nullable=True)

    @property
    def effective_selling_rate(self):
        """The rate an Estimate/Order should actually use - the manual
        override if one was recorded, otherwise the calculated
        woodful_selling_rate. Never silently picks one without the
        caller being able to see which (override_price is still
        visible separately)."""
        return self.override_price if self.override_price is not None else self.woodful_selling_rate
