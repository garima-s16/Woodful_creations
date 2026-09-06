"""Inventory domain models: Location, MaterialCategory,
MaterialSubcategory, MaterialAttributeDefinition,
MaterialAttributeValue, Material, StockTransfer, StockAdjustment,
StockLedgerEntry.

Supplier/SupplierMaterial/Purchase moved to
app.modules.procurement.models (Family 130 P0.2 ownership correction -
procurement owns suppliers and purchases; inventory owns physical
stock). Relationships to them below are string-based ("Supplier",
"Purchase"), which SQLAlchemy resolves via its mapper registry, not a
direct Python import - no circular-import risk from the split.

Consolidated from material.py + material_category.py + location.py +
stock_ledger_entry.py + stock_transaction.py.
"""
from sqlalchemy import Column, String, Integer, Numeric, Boolean, Text, ForeignKey, DateTime, UniqueConstraint, func
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from datetime import datetime
from app.platform.database.base import BaseModel


class Location(BaseModel):
    """A flexible, arbitrary-depth location tree (Warehouse -> Area ->
    Rack -> Bin, or as few/many levels as a business actually uses) -
    self-referential rather than four rigid fixed tables, since not
    every material needs bin-level precision and users must be able to
    define their own structure without a schema change.
    location_type is a free-text hint for display/grouping ("Warehouse",
    "Rack", "Chemical Area"), not an enforced enum - matching the
    product principle that nothing important is hard-coded."""
    __tablename__ = "locations"
    __table_args__ = (UniqueConstraint("parent_id", "name", name="uq_location_name_per_parent"),)

    business_id = Column(String(10), unique=True, index=True, nullable=True)
    name = Column(String(150), nullable=False, index=True)
    location_type = Column(String(50), nullable=True)  # "Warehouse", "Area", "Rack", "Bin", or user-defined
    parent_id = Column(Integer, ForeignKey("locations.id"), nullable=True, index=True)

    parent = relationship("Location", remote_side="Location.id", backref="children")

    @property
    def full_path(self):
        """"Vijay Nagar Warehouse > Rack A2 > Bin H1" - built by walking
        up the parent chain, so the UI can show exactly where something
        is without a separate denormalized path column to keep in sync."""
        parts = [self.name]
        node = self.parent
        seen_ids = {self.id}  # defensive - a corrupted parent cycle must not infinite-loop
        while node and node.id not in seen_ids:
            parts.append(node.name)
            seen_ids.add(node.id)
            node = node.parent
        return " > ".join(reversed(parts))


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


class MaterialAttributeDefinition(BaseModel):
    """Defines what specification fields make sense for a subcategory -
    e.g. Plywood needs Brand/Grade/Thickness/Sheet Length/Sheet Width;
    LED Strip needs Voltage/Wattage/Colour Temperature. Each subcategory
    defines its own set rather than every material sharing one rigid
    universal column list."""
    __tablename__ = "material_attribute_definitions"
    __table_args__ = (UniqueConstraint("subcategory_id", "name", name="uq_attribute_per_subcategory"),)

    subcategory_id = Column(Integer, ForeignKey("material_subcategories.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)  # "Thickness", "Voltage", "Colour Temperature"
    data_type = Column(String(20), nullable=False, default="text")  # text / number / select
    unit_label = Column(String(20), nullable=True)  # "mm", "V", "K" - display only, not parsed
    # Comma-separated allowed values, only meaningful when data_type="select"
    # (e.g. "Matte,Glossy,Textured" for a laminate Finish attribute).
    select_options = Column(String(500), nullable=True)
    is_required = Column(Boolean, nullable=False, default=False)
    sort_order = Column(Integer, nullable=False, default=0)

    subcategory = relationship("MaterialSubcategory", back_populates="attribute_definitions")


class MaterialAttributeValue(BaseModel):
    """The actual value of one attribute for one material. Stored in a
    typed column matching the attribute's data_type (value_number for
    numeric attributes, value_text for text/select) rather than a single
    stringified column, so numeric attributes can actually be filtered
    and sorted with real SQL comparisons (thickness > 12), not string
    parsing - this is the "supports filtering/searching/reporting"
    requirement, not just a display convenience."""
    __tablename__ = "material_attribute_values"
    __table_args__ = (UniqueConstraint("material_id", "attribute_definition_id", name="uq_value_per_material_attribute"),)

    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)
    attribute_definition_id = Column(Integer, ForeignKey("material_attribute_definitions.id"), nullable=False, index=True)
    value_text = Column(String(255), nullable=True)
    value_number = Column(Numeric(14, 4), nullable=True, index=True)

    material = relationship("Material", back_populates="attribute_values")
    attribute_definition = relationship("MaterialAttributeDefinition")

    @property
    def attribute_name(self):
        return self.attribute_definition.name if self.attribute_definition else None

    @property
    def display_value(self):
        if self.value_number is not None:
            unit = self.attribute_definition.unit_label if self.attribute_definition else None
            num_str = f"{self.value_number:g}"
            return f"{num_str} {unit}".strip() if unit else num_str
        return self.value_text or ""


class Material(BaseModel):
    """Live Material Stock Master. current_stock/total_purchased/total_issued
    are maintained transactionally by StockService whenever a Purchase or
    Issue is recorded - see modules/inventory/stock_service.py."""
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

    # Numeric, not Integer - a material measured in kg/litres/metres
    # needs real decimal precision (2.5 kg of adhesive), not silent
    # rounding. Every write to these must flow through StockService
    # using Decimal arithmetic, never int() truncation.
    opening_stock = Column(Numeric(12, 2), nullable=False, default=0)
    total_purchased = Column(Numeric(12, 2), nullable=False, default=0)
    total_issued = Column(Numeric(12, 2), nullable=False, default=0)
    current_stock = Column(Numeric(12, 2), nullable=False, default=0, index=True)
    minimum_stock = Column(Numeric(12, 2), nullable=False, default=0)

    average_rate = Column(Numeric(12, 2), nullable=False, default=0)
    # Default True - every existing material stays exactly as visible/
    # usable as before. An inactive material is kept for its purchase/
    # issue history, not deleted, but is excluded from active-catalog
    # listings and reorder suggestions.
    is_active = Column(Boolean, nullable=False, default=True)

    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True, index=True)
    # Kept for backward compatibility - existing consumers read this
    # directly. When location_id is set, this is derived server-side
    # from the Location's full_path, not taken from client input.
    location = Column(String(100), nullable=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True, index=True)
    # Where opening_stock lives, captured once (at creation) rather than
    # re-derived from location_id on every read - location_id can be
    # edited later (a material's primary location can genuinely change),
    # and opening_stock's original location must not silently move along
    # with it. See migration 0061.
    opening_stock_location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)

    primary_supplier = relationship("Supplier", back_populates="materials")
    purchases = relationship("Purchase", back_populates="material")
    issues = relationship("Issue", back_populates="material")
    subcategory = relationship("MaterialSubcategory", back_populates="materials")
    attribute_values = relationship("MaterialAttributeValue", back_populates="material",
                                     cascade="all, delete-orphan")
    supplier_materials = relationship("SupplierMaterial", back_populates="material", cascade="all, delete-orphan")
    location_ref = relationship("Location", foreign_keys=[location_id])

    @hybrid_property
    def stock_value(self):
        return round(float(self.current_stock or 0) * float(self.average_rate or 0), 2)

    @stock_value.expression
    def stock_value(cls):
        # No rounding at the SQL-expression level deliberately - this is
        # used for aggregation (SUM across many rows), where rounding
        # each row before summing would not equal rounding the final
        # total. Callers that need a rounded total round the aggregate
        # result themselves, the same way the instance getter above
        # rounds a single value.
        return func.coalesce(cls.current_stock, 0) * func.coalesce(cls.average_rate, 0)

    @property
    def stock_status(self):
        if (self.current_stock or 0) <= 0:
            return "OUT OF STOCK"
        if (self.current_stock or 0) <= (self.minimum_stock or 0):
            return "LOW STOCK"
        return "STOCK OK"


class StockTransfer(BaseModel):
    """A real, audited record of moving a material from one location to
    another. Material.location_id is a single field (no per-location
    quantity breakdown - see docs/UI_UX_BACKLOG.md item 1 on why that's
    deliberately deferred until the full stock ledger exists), so a
    transfer here means: log the move, then update that single field -
    not maintain a second, parallel stock-by-location number."""
    __tablename__ = "stock_transfers"

    business_id = Column(String(10), unique=True, index=True, nullable=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)
    quantity = Column(Numeric(12, 2), nullable=False)
    from_location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    to_location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    transferred_by = Column(String(100), nullable=True)
    remarks = Column(Text, nullable=True)

    material = relationship("Material")
    from_location = relationship("Location", foreign_keys=[from_location_id])
    to_location = relationship("Location", foreign_keys=[to_location_id])


class StockAdjustment(BaseModel):
    """An audited correction to current_stock - never a silent direct
    edit. Every adjustment records a reason and a signed quantity delta
    (positive = increase, negative = decrease), same accountability
    pattern already used for Purchase (+stock) and Issue (-stock)."""
    __tablename__ = "stock_adjustments"

    business_id = Column(String(10), unique=True, index=True, nullable=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)
    adjustment_type = Column(String(30), nullable=False)  # Physical Count / Damage / Wastage / Theft-Loss / Correction / Return from Issue
    related_issue_id = Column(Integer, ForeignKey("issues.id"), nullable=True, index=True)  # set only for adjustment_type="Return from Issue"
    quantity_delta = Column(Numeric(12, 2), nullable=False)  # signed: +5 or -5
    stock_before = Column(Numeric(12, 2), nullable=False)
    stock_after = Column(Numeric(12, 2), nullable=False)
    reason = Column(Text, nullable=False)
    adjusted_by = Column(String(100), nullable=True)
    # Which location the adjustment applies to. Nullable - unset means
    # "the material's primary location", preserving behavior for existing
    # callers that don't pass one.
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True, index=True)

    material = relationship("Material")
    location = relationship("Location")


class StockLedgerEntry(BaseModel):
    """One immutable row per stock-affecting event - Receipt (purchase
    or return), Issue, Adjustment, or Transfer. Never updated or deleted
    once written. balance_after records the running material-wide
    current_stock immediately after this entry, so the ledger can be
    replayed and checked against Material.current_stock at any time
    (StockService.verify_stock_matches_ledger does exactly this).
    reference_type/reference_id link back to the actual Purchase/
    Issue/StockAdjustment/StockTransfer row that caused the change, so
    every number here traces to a real business record - never a
    synthetic entry.

    location_id identifies WHERE the movement happened - nullable for
    backward compatibility with entries written before multi-location
    support existed. A Transfer is recorded as two entries (a negative
    delta at from_location, a positive delta at to_location) whose
    quantity_delta sums to zero, so the material-wide total (and
    verify_stock_matches_ledger) is completely unaffected by transfers -
    only the per-location breakdown changes. Per-location balance is
    always DERIVED by summing quantity_delta grouped by location_id -
    never stored as an independent number (see
    StockService.get_location_balances).
    """
    __tablename__ = "stock_ledger_entries"

    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)
    entry_type = Column(String(20), nullable=False)  # Receipt / Issue / Adjustment / Transfer
    quantity_delta = Column(Numeric(12, 2), nullable=False)  # signed: +5 or -5
    balance_after = Column(Numeric(12, 2), nullable=False)
    reference_type = Column(String(20), nullable=True)  # purchase / issue / stock_adjustment / stock_transfer
    reference_id = Column(Integer, nullable=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True, index=True)
    remarks = Column(Text, nullable=True)

    material = relationship("Material")
    location = relationship("Location")
