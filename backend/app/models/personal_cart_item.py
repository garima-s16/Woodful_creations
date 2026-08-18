from sqlalchemy import Column, String, Integer, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class PersonalCartItem(BaseModel):
    """One line of a user's personal procurement cart - the database is
    the source of truth (never localStorage/Redux-only), so it survives
    logout/login and browser changes. A cart is 1:1 with a user, so
    user_id directly identifies whose cart a row belongs to - no
    separate PersonalCart header table needed for that.

    Adding an item here does NOT touch inventory, does NOT create a
    Purchase, and does NOT affect any other user's cart - it's purely a
    personal request list until explicitly sent to the Mastercart.

    Snapshots material_name/unit at add-time (Section 11's explicit
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
