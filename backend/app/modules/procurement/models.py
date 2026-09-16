"""Procurement domain models: Supplier, SupplierMaterial, Purchase,
ProcurementRequirement, SupplierDecision, PersonalCartItem.

Supplier/SupplierMaterial/Purchase moved here from
app.modules.inventory.models (Family 130 P0.2 ownership correction) -
procurement owns suppliers and the purchase business record; inventory
(Material, stock ledger, physical mutation) remains the authority for
actual stock quantities. Relationships below to Material/Order use
string references, resolved via SQLAlchemy's mapper registry rather
than a direct Python import, so this file does not import from
inventory/sales - no circular-import risk from the split.
"""
from sqlalchemy import Column, String, Integer, Numeric, Boolean, ForeignKey, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.platform.database import BaseModel
from typing import Optional
from decimal import Decimal
from app.modules.inventory.schemas import PURCHASE_CREATE_RECEIPT_STATUSES


PROCUREMENT_REQUIREMENT_STATUSES = {"Open", "Ordered", "Fulfilled", "Cancelled"}


class Supplier(BaseModel):
    __tablename__ = "suppliers"

    supplier_code = Column(String(20), unique=True, nullable=False, index=True)  # SUP-001
    # Opaque 10-char external identifier (e.g. A7K92P4XQ1) - separate from
    # supplier_code, which stays as the human-scannable sequential reference.
    business_id = Column(String(10), unique=True, index=True, nullable=True)
    name = Column(String(255), nullable=False, index=True)
    category = Column(String(100), nullable=True)
    contact_person = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    gstin = Column(String(20), nullable=True)
    payment_terms = Column(String(50), nullable=True)
    remarks = Column(Text, nullable=True)

    materials = relationship("Material", back_populates="primary_supplier")
    purchases = relationship("Purchase", back_populates="supplier")
    supplier_materials = relationship("SupplierMaterial", back_populates="supplier", cascade="all, delete-orphan")


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
    # exact supplier+material pair (see ProcurementService.record_purchase) -
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


class Purchase(BaseModel):
    """Stock In / Purchase Register."""
    __tablename__ = "purchases"

    purchase_code = Column(String(20), unique=True, nullable=False, index=True)  # PUR-001
    # Opaque 10-char external identifier (e.g. A7K92P4XQ1) - separate from
    # purchase_code, which stays as the human-scannable sequential reference.
    business_id = Column(String(10), unique=True, index=True, nullable=True)
    date = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    expected_delivery_date = Column(DateTime, nullable=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)
    quantity = Column(Numeric(12, 2), nullable=False)
    unit = Column(String(20), nullable=False)
    rate = Column(Numeric(12, 2), nullable=False)
    taxable_value = Column(Numeric(12, 2), nullable=False)
    gst_percent = Column(Numeric(5, 2), nullable=False, default=0)
    gst_amount = Column(Numeric(12, 2), nullable=False, default=0)
    invoice_total = Column(Numeric(12, 2), nullable=False)
    payment_status = Column(String(20), nullable=False, default="Paid")
    # "Received" (default) - stock increases immediately, the only
    # behavior that existed before this field. "Ordered" - goods
    # requested from the supplier but not yet arrived; stock is
    # untouched until ProcurementService.mark_purchase_received is called.
    # "Partially Received" - some but not all of `quantity` has
    # arrived; quantity_received tracks how much.
    receipt_status = Column(String(20), nullable=False, default="Received")
    quantity_received = Column(Numeric(12, 2), nullable=False, default=0)  # how much of `quantity` has actually arrived
    # Which location this purchase's stock is/was received into. Nullable -
    # unset means "use the material's primary location", preserving
    # behavior for callers that don't pass one. Kept on the Purchase itself
    # (not just the ledger entry) so an "Ordered" purchase remembers where
    # it's destined until ProcurementService.mark_purchase_received actually
    # applies the receipt.
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True, index=True)

    supplier = relationship("Supplier", back_populates="purchases")
    material = relationship("Material", back_populates="purchases")
    location = relationship("Location")


class ProcurementRequirement(BaseModel):
    """A persisted procurement decision object (P0.2.1) - created when
    a Master acts on a shortage the authoritative material requirement
    calculation (StockService.calculate_order_material_requirements)
    already identified. This is NOT a second shortage engine: it
    snapshots that calculation's result at the moment a Master decides
    "yes, procure this" (required/available/shortage as of right now),
    so the requirement stays a meaningful, traceable record even as
    stock later changes - the live, current figure remains available
    fresh from the same authoritative calculation for comparison,
    never recomputed or duplicated here.

    status tracks the requirement's own lifecycle (Open -> Ordered ->
    Fulfilled, or Cancelled) - distinct from Purchase.receipt_status,
    which tracks the separate lifecycle of the resulting purchase once
    one exists."""
    __tablename__ = "procurement_requirements"

    business_id = Column(String(10), unique=True, index=True, nullable=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)
    required_quantity = Column(Numeric(12, 2), nullable=False)
    available_quantity_at_creation = Column(Numeric(12, 2), nullable=False)
    shortage_quantity_at_creation = Column(Numeric(12, 2), nullable=False)
    status = Column(String(20), nullable=False, default="Open", index=True)  # Open / Ordered / Fulfilled / Cancelled
    priority = Column(String(20), nullable=True)
    required_by_date = Column(DateTime, nullable=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=True, index=True)
    remarks = Column(Text, nullable=True)
    created_by = Column(String(255), nullable=True)

    order = relationship("Order")
    material = relationship("Material")
    purchase = relationship("Purchase")
    decision = relationship("SupplierDecision", back_populates="requirement", uselist=False)


class SupplierDecision(BaseModel):
    """The genuine gap identified in this family's own P0.2 review: the
    system already computes supplier recommendations (price/lead-time/
    preferred, see ProcurementService._supplier_options_for_materials), but
    never persisted which supplier was actually recommended versus
    which one a Master actually chose - a Purchase's supplier_id alone
    cannot answer "did we follow the recommendation, and if not, why".
    This record captures that decision once, at the moment it is made -
    recommended_supplier_id/reason are a frozen snapshot of what the
    recommendation said at decision time (not re-derived later), since
    a later purchase or price change must never retroactively change
    what was actually recommended when the Master decided."""
    __tablename__ = "supplier_decisions"

    business_id = Column(String(10), unique=True, index=True, nullable=True)
    requirement_id = Column(Integer, ForeignKey("procurement_requirements.id"), nullable=False, unique=True, index=True)
    recommended_supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    recommended_reason = Column(String(255), nullable=True)  # e.g. "lower rate + shorter lead time"
    selected_supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    decision_reason = Column(String(255), nullable=True)
    decided_by = Column(String(255), nullable=True)

    requirement = relationship("ProcurementRequirement", back_populates="decision")
    recommended_supplier = relationship("Supplier", foreign_keys=[recommended_supplier_id])
    selected_supplier = relationship("Supplier", foreign_keys=[selected_supplier_id])

    @property
    def followed_recommendation(self):
        """True only when a real recommendation existed and the
        selected supplier matches it exactly - None (not True/False)
        when there was no recommendation to compare against, so this
        is never misread as "didn't follow advice" when no advice was
        actually given."""
        if self.recommended_supplier_id is None:
            return None
        return self.selected_supplier_id == self.recommended_supplier_id


class PersonalCartItem(BaseModel):
    """One line of a user's personal procurement cart - the database is
    the source of truth (never localStorage/Redux-only), so it survives
    logout/login and browser changes. A cart is 1:1 with a user, so
    user_id directly identifies whose cart a row belongs to - no
    separate PersonalCart header table needed for that.

    Adding an item here does NOT touch inventory, does NOT create a
    Purchase, and does NOT affect any other user's cart - it's purely a
    personal request list until explicitly sent to the Mastercart.

    Snapshots material_name/unit at add-time (the explicit
    "preserve a snapshot... but do not duplicate the entire material
    database") so the cart still displays meaningfully even if the
    material is later renamed - material_id is still the live FK for
    anything that needs current data (price, stock)."""
    __tablename__ = "personal_cart_items"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)
    material_name = Column(String(255), nullable=False)  # snapshot at add-time
    unit = Column(String(20), nullable=True)
    quantity = Column(Numeric(10, 2), nullable=False, default=1)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    supplier_name = Column(String(255), nullable=True)  # snapshot at add-time
    rate = Column(Numeric(12, 2), nullable=True)
    note = Column(String(500), nullable=True)
    # ACTIVE / SUBMITTED (sent to Mastercart) - CART_STATUS in the brief;
    # only these two are implemented this pass, since Mastercart itself
    # (which would consume SUBMITTED items) is a separate, larger system.
    status = Column(String(20), nullable=False, default="ACTIVE")

    user = relationship("User")
    material = relationship("Material")
    supplier = relationship("Supplier")
