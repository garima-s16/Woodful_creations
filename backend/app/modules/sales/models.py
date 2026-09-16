"""Sales transaction domain models: Estimate, EstimateLineItem, Order,
OrderItem, OrderComment, Payment, PaymentDocument.

Consolidated from estimate.py + order.py + payment.py.
"""
from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.orm import relationship
from decimal import Decimal
from datetime import datetime
from app.platform.database import BaseModel
from typing import Optional, List


WHOLE_NUMBER_UNITS = {
    "piece", "pieces", "pcs", "pc", "set", "sets", "pair", "pairs",
    "nos", "no", "box", "boxes", "roll", "rolls", "bundle", "bundles",
    "sheet", "sheets", "job", "jobs",
}


def quantity_violates_whole_unit_rule(quantity: Decimal, unit) -> bool:
    if not unit or unit.strip().lower() not in WHOLE_NUMBER_UNITS:
        return False
    return quantity != quantity.to_integral_value()


"""Sales domain schemas - estimates, orders, and payments. Consolidated
from three separate modules: genuinely tightly coupled (an order can be
converted from an estimate and copies its line items; a payment always
references an order), not three independent concerns.

estimate_import.py and order_import.py are deliberately NOT included
here - they're bulk-import infrastructure, a different concern from
this module's core CRUD schemas."""


LINE_ITEM_CATEGORIES = [
    "Material", "Labor", "Furniture", "Hardware", "Installation", "Transportation", "Design", "Service", "Other",
]


ORDER_PRIORITIES = {"Low", "Medium", "High", "Urgent"}


PAYMENT_TYPES = ("Advance", "Progress Payment", "Internal")


class Estimate(BaseModel):
    """Cost estimate for a client/order - material + labor cost, tax,
    total. Independent of Order.order_value so a client can be quoted
    before an order is confirmed."""
    __tablename__ = "estimates"

    estimate_code = Column(String(20), unique=True, nullable=False, index=True)  # EST-001
    # Opaque 10-char external identifier (e.g. A7K92P4XQ1) - separate from
    # estimate_code, which stays as the human-scannable sequential reference.
    business_id = Column(String(10), unique=True, index=True, nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    description = Column(Text, nullable=True)
    # material_cost/labor_cost remain for backward compatibility with
    # estimates created before line items existed - a new estimate with
    # real line items drives its totals from the sum of those instead
    # (see subtotal property below).
    material_cost = Column(Numeric(12, 2), nullable=False, default=0)
    labor_cost = Column(Numeric(12, 2), nullable=False, default=0)
    discount = Column(Numeric(12, 2), nullable=False, default=0)
    tax_percent = Column(Numeric(5, 2), nullable=False, default=18)
    # Estimate-specific margin override (pricing priority level 4, see
    # app/modules/catalog/pricing.py) - applies to this estimate's line
    # items that don't have a more specific override (explicit
    # line-item price or customer-specific pricing), without touching
    # any Product's own global margin_percent.
    margin_percent_override = Column(Numeric(5, 2), nullable=True)
    tax_amount = Column(Numeric(12, 2), nullable=False, default=0)
    total_cost = Column(Numeric(12, 2), nullable=False, default=0)
    status = Column(String(20), nullable=False, default="draft", index=True)  # draft/sent/approved/rejected/changes_requested/...
    valid_until = Column(DateTime, nullable=True)
    remarks = Column(Text, nullable=True)

    # Family 137, feature 1 - Client Approval Hub. Set only via the
    # client-facing portal (clients/portal_api.py), never by internal
    # staff editing - approved_by is the client's own typed name, not
    # a staff member's. client_decision_comments holds whichever note
    # the client left, whether approving or requesting changes -
    # kept even after approval, since "approved, but please double
    # check the veneer colour" is a real, useful comment to retain.
    approved_by = Column(String(255), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    client_decision_comments = Column(Text, nullable=True)

    # Versioning: revising an estimate creates a new row rather than
    # overwriting history. version 1 has parent_estimate_id = None; every
    # revision points back to the same root via parent_estimate_id.
    version = Column(Integer, nullable=False, default=1)
    parent_estimate_id = Column(Integer, ForeignKey("estimates.id"), nullable=True, index=True)

    client = relationship("Client")
    order = relationship("Order", back_populates="estimates")
    parent_estimate = relationship("Estimate", remote_side="Estimate.id", backref="revisions")
    line_items = relationship("EstimateLineItem", back_populates="estimate",
                               cascade="all, delete-orphan", order_by="EstimateLineItem.sort_order")

    @property
    def subtotal(self):
        """Sum of line item amounts if any exist; falls back to the legacy
        material_cost + labor_cost for estimates created before line
        items existed, so old records still compute a correct total."""
        if self.line_items:
            return sum((item.amount or Decimal("0") for item in self.line_items), Decimal("0"))
        return (self.material_cost or Decimal("0")) + (self.labor_cost or Decimal("0"))


class EstimateLineItem(BaseModel):
    """A single priced item within an estimate - e.g. "Wardrobe",
    "Hardware", "Installation". Real per-item quantity/rate/amount, not a
    single flat material+labor figure - so an estimate can actually
    itemize what a client is being quoted for, not just a total."""
    __tablename__ = "estimate_line_items"

    estimate_id = Column(Integer, ForeignKey("estimates.id"), nullable=False, index=True)
    description = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)  # Material/Labor/Hardware/Installation/Transportation/Design/...
    quantity = Column(Numeric(10, 2), nullable=False, default=1)
    unit = Column(String(20), nullable=True)
    rate = Column(Numeric(12, 2), nullable=False, default=0)
    amount = Column(Numeric(12, 2), nullable=False, default=0)  # quantity * rate, stored (not computed at read time)
    sort_order = Column(Integer, nullable=False, default=0)
    # Optional link to the Product Master - what was actually quoted, when
    # it corresponds to a real catalog/custom product rather than a
    # freeform line (e.g. "Design consultation"). Nullable: an estimate
    # line item is never required to reference a product.
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    # Custom/one-off line item (spec section 15): a genuine customer
    # request that doesn't exist in Product Master and shouldn't be
    # forced into it. When True, product_id stays null and this line
    # is exempt from the "Product ID is required" rule - description/
    # rate are still required as normal.
    is_custom_item = Column(Boolean, nullable=False, default=False)
    # Historical pricing snapshot (spec section 13): which priority
    # rule actually produced this line's rate, and the margin% used if
    # any - recorded once at creation and never recalculated, so a
    # later change to the Product's margin, a RateCard revision, or a
    # customer-specific override can never retroactively change what
    # this specific historical line says it charged.
    pricing_rule_applied = Column(String(40), nullable=True)  # one of app.modules.catalog.pricing.PRICING_RULES
    applied_margin_percent = Column(Numeric(5, 2), nullable=True)
    # Cost basis (Product.cost_price or suggested_cost_price) at the moment
    # this line was priced - the missing half of pricing_rule_applied/
    # applied_margin_percent needed to detect Cost-Drift (Family 137,
    # feature 9): those two record what pricing DECISION was made, this
    # records what the underlying COST actually was at that time, so a
    # later change in material/product cost is a comparison against a
    # real number, not a guess. Nullable and never backfilled for rows
    # created before this column existed - "unknown", not zero, matching
    # Issue.rate_at_issue's convention above.
    cost_at_creation = Column(Numeric(12, 2), nullable=True)

    estimate = relationship("Estimate", back_populates="line_items")
    product = relationship("Product", back_populates="estimate_line_items")

    @property
    def product_name(self):
        return self.product.name if self.product else None

    @property
    def product_code(self):
        return self.product.product_code if self.product else None


class Order(BaseModel):
    """Order & Project Management. total_received/balance are derived from
    advance + other_received (kept as stored columns for fast dashboard
    reads, maintained transactionally by OrderService alongside Payments)."""
    __tablename__ = "orders"

    order_code = Column(String(20), unique=True, nullable=False, index=True)  # WC-2026-001
    # Opaque 10-char external identifier (e.g. A7K92P4XQ1) - separate from
    # order_code, which stays as the human-scannable sequential reference.
    business_id = Column(String(10), unique=True, index=True, nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    project_type = Column(String(100), nullable=True)
    order_date = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    delivery_date = Column(DateTime, nullable=True)
    order_value = Column(Numeric(12, 2), nullable=False, default=0)
    # discount is an absolute amount (same meaning as Estimate.discount,
    # not a percentage) - see app/modules/sales/services.py's compute_totals function, the same
    # formula both entities now share. order_value itself IS the grand
    # total (what the client actually owes), computed server-side as
    # items_subtotal - discount + tax_amount.
    discount = Column(Numeric(12, 2), nullable=False, default=0)
    tax_percent = Column(Numeric(5, 2), nullable=False, default=18)
    tax_amount = Column(Numeric(12, 2), nullable=False, default=0)
    advance = Column(Numeric(12, 2), nullable=False, default=0)
    other_received = Column(Numeric(12, 2), nullable=False, default=0)
    total_received = Column(Numeric(12, 2), nullable=False, default=0)
    balance = Column(Numeric(12, 2), nullable=False, default=0)
    project_status = Column(String(50), nullable=False, default="Enquiry", index=True)
    design_status = Column(String(50), nullable=False, default="Pending")
    execution_status = Column(String(50), nullable=False, default="Pending")
    delivery_status = Column(String(50), nullable=False, default="Pending")
    progress_percent = Column(Integer, nullable=False, default=0)
    priority = Column(String(20), nullable=True)
    supervisor = Column(String(255), nullable=True)
    site_address = Column(Text, nullable=True)
    remarks = Column(Text, nullable=True)

    client = relationship("Client", back_populates="orders")
    payments = relationship("Payment", back_populates="order")
    expenses = relationship("ProjectExpense", back_populates="order")
    issues = relationship("Issue", back_populates="order")
    daily_tasks = relationship("DailyTask", back_populates="order")
    production_jobs = relationship("ProductionJob", back_populates="order")
    estimates = relationship("Estimate", back_populates="order")
    milestones = relationship("Milestone", back_populates="order", cascade="all, delete-orphan")
    items = relationship("OrderItem", back_populates="order",
                          cascade="all, delete-orphan", order_by="OrderItem.sort_order")

    @property
    def source_estimate(self):
        """The estimate this order was converted from, if any - derived
        from the estimates relationship (the FK actually lives on
        Estimate.order_id) rather than duplicated as a stored column.
        At most one, in practice: the atomic claim in the order-creation
        route (see orders.py) means only one estimate can ever end up
        pointing order_id at a given order."""
        return self.estimates[0] if self.estimates else None

    @property
    def source_estimate_id(self):
        return self.source_estimate.id if self.source_estimate else None

    @property
    def source_estimate_code(self):
        return self.source_estimate.estimate_code if self.source_estimate else None

    @property
    def items_subtotal(self):
        """Sum of item amounts if any exist; None when there are no
        items, so callers can tell "no scope entered" apart from a
        genuine zero-value order."""
        if not self.items:
            return None
        return sum((item.amount or Decimal("0") for item in self.items), Decimal("0"))

    @property
    def payment_status(self):
        """Derived from balance/total_received - computed once here so
        every consumer (dashboard, PDF, Excel, chatbot, frontend) reads
        the same value rather than each working it out independently."""
        if not self.order_value:
            return "N/A"
        if self.total_received and self.total_received >= self.order_value:
            return "Paid"
        if self.total_received and self.total_received > 0:
            return "Partially Paid"
        return "Unpaid"

    def recompute_totals(self):
        """Call after adding/editing a Payment - keeps total_received and
        balance consistent with the advance recorded at order creation
        plus the sum of this order's Payment rows. The advance is stored
        directly on the order, not as its own Payment record, so it must
        be added back in explicitly here - omitting it was a real bug:
        total_received would silently drop to just the newest payment
        the moment any payment was recorded after order creation,
        making the advance disappear from the running total."""
        payments_total = sum((p.amount for p in self.payments), Decimal("0")) if self.payments else Decimal("0")
        total = (self.advance or Decimal("0")) + payments_total
        self.total_received = total
        self.balance = (self.order_value or Decimal("0")) - total


class OrderItem(BaseModel):
    """A single scoped item within an order - what the client actually
    ordered, not just a lump order_value. When an order is created from
    an estimate, its items are copied in from that estimate's line
    items (source_estimate_item_id records where each one came from,
    so the two stay traceable without duplicating unrelated data)."""
    __tablename__ = "order_items"

    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    description = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)
    quantity = Column(Numeric(10, 2), nullable=False, default=1)
    unit = Column(String(20), nullable=True)
    rate = Column(Numeric(12, 2), nullable=False, default=0)
    amount = Column(Numeric(12, 2), nullable=False, default=0)  # quantity * rate, server-computed
    source_estimate_item_id = Column(Integer, ForeignKey("estimate_line_items.id"), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    # Optional link to the Product Master - identifies exactly what was
    # ordered, when it corresponds to a real catalog/custom product.
    # Nullable: an order item is never required to reference a product
    # (freeform lines like "Installation" stay freeform).
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    is_custom_item = Column(Boolean, nullable=False, default=False)
    pricing_rule_applied = Column(String(40), nullable=True)
    applied_margin_percent = Column(Numeric(5, 2), nullable=True)

    order = relationship("Order", back_populates="items")
    source_estimate_item = relationship("EstimateLineItem")
    product = relationship("Product", back_populates="order_items")

    @property
    def product_name(self):
        """Lets the Order Detail screen show the actual Product Master
        name for a linked item, not just whatever the free-text
        description happens to say."""
        return self.product.name if self.product else None

    @property
    def product_code(self):
        return self.product.product_code if self.product else None


class OrderComment(BaseModel):
    """Project-level communication tied to an Order - the same simple
    practical pattern as TaskComment (see app/modules/operations/models.py), just
    scoped to the whole project rather than one task. Deliberately not a
    generic/parent-type comment table: an Order-level thread and a
    task-level thread serve different audiences (project-wide context
    vs. one specific job), so keeping them as separate, purpose-built
    tables - matching how TaskComment was already built - is clearer
    than a single polymorphic comments table would be."""
    __tablename__ = "order_comments"

    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    author = Column(String(255), nullable=False)
    text = Column(Text, nullable=False)
    date = Column(DateTime, nullable=False, default=datetime.utcnow)

    order = relationship("Order")


class Payment(BaseModel):
    """Client Payment Register."""
    __tablename__ = "payments"

    receipt_code = Column(String(20), unique=True, nullable=False, index=True)  # RCPT-001
    # Opaque 10-char external identifier (e.g. A7K92P4XQ1) - separate from
    # receipt_code, which stays as the human-scannable sequential reference.
    business_id = Column(String(10), unique=True, index=True, nullable=True)
    date = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    payment_type = Column(String(50), nullable=False)  # Advance / Progress Payment / Internal
    payment_mode = Column(String(50), nullable=False)  # Cash / UPI / Bank Transfer / Cheque / Card / Other
    amount = Column(Numeric(12, 2), nullable=False, default=0)
    reference_number = Column(String(100), nullable=True)
    received_by = Column(String(255), nullable=True)
    remarks = Column(Text, nullable=True)

    order = relationship("Order", back_populates="payments")
    documents = relationship("PaymentDocument", back_populates="payment", cascade="all, delete-orphan")


class PaymentDocument(BaseModel):
    """Proof of a payment - a scanned cheque, UPI screenshot, bank
    transfer receipt. stored_filename is a random, server-generated
    name (never the user-supplied original), matching the exact same
    path-traversal protection already established for client
    documents and candidate resumes.

    storage_backend/drive_file_id - see GenericDocument's docstring
    for the full explanation; identical pattern here."""
    __tablename__ = "payment_documents"

    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False, unique=True)
    content_type = Column(String(100), nullable=True)
    description = Column(String(255), nullable=True)
    uploaded_by = Column(String(100), nullable=True)
    storage_backend = Column(String(20), nullable=False, default="local")
    drive_file_id = Column(String(255), nullable=True, index=True)

    payment = relationship("Payment", back_populates="documents")


APPROVED_SPECIFICATION_STATUSES = ("approved", "superseded", "change_requested")


class ApprovedSpecification(BaseModel):
    """Approved Specification / Sample Lock (Family 137, feature 8).

    The authoritative, versioned record of the exact material/finish/
    hardware specification a client actually approved for an Order -
    captured at the moment of approval, never edited in place. This
    exists to eliminate disputes like "this isn't the colour I
    approved": there is a literal, dated, photographed record of what
    was shown and who approved it.

    Versioned the same way Estimate is (version / a self-referencing
    predecessor link) rather than allowing an update: a change request
    creates a brand-new row pointing back at supersedes_id, and the
    old row's status flips to "superseded" - it is never overwritten
    or deleted, so the full approval history for an order is always
    reconstructable.
    """
    __tablename__ = "approved_specifications"

    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    supersedes_id = Column(Integer, ForeignKey("approved_specifications.id"), nullable=True)

    material = Column(String(255), nullable=True)
    finish = Column(String(255), nullable=True)
    veneer = Column(String(255), nullable=True)
    laminate = Column(String(255), nullable=True)
    colour = Column(String(100), nullable=True)
    hardware = Column(String(255), nullable=True)
    # Which physical batch/reference the approved sample came from - the
    # detail that actually resolves a "this doesn't match" dispute, since
    # two batches of the "same" material/finish can still look different.
    batch_reference = Column(String(100), nullable=True)
    sample_photo_path = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)

    # approved: the current authoritative spec for this order.
    # superseded: a prior version, kept for history, no longer authoritative.
    # change_requested: a superseded version's replacement is pending a new approval.
    status = Column(String(20), nullable=False, default="approved")
    approved_by = Column(String(255), nullable=True)  # the client/person who approved it, not the staff member recording it
    approved_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    recorded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # the staff member who logged the approval

    order = relationship("Order")
    supersedes = relationship("ApprovedSpecification", remote_side="ApprovedSpecification.id")
