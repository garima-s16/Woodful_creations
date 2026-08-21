from sqlalchemy import Column, String, Numeric, Boolean, Text, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


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
    previous one (see app/api/routes/rate_cards.py), so any Estimate/
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
    # final numbers - see app/utils/pricing_engine.py, the one place
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
