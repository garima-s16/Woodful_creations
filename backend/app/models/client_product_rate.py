from sqlalchemy import Column, String, Numeric, Text, ForeignKey, UniqueConstraint, Integer
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class ClientProductRate(BaseModel):
    """A customer-specific commercial override for one Product - never
    modifies the global Product.selling_price/margin_percent or any
    RateCard; this is a separate, additive layer (spec section 11:
    "A customer-specific negotiated rate must NOT modify the global
    Rate Master... Global rate remains Rs 10,000").

    Exactly one of (margin_percent, fixed_selling_price) is expected to
    be set - margin_percent overrides just the margin (letting cost
    changes still flow through), fixed_selling_price is a direct
    negotiated number that ignores cost/margin entirely. Both stay
    nullable rather than an enum + single value column, since either
    is a legitimate, independently useful override shape.
    """
    __tablename__ = "client_product_rates"
    __table_args__ = (UniqueConstraint("client_id", "product_id", name="uq_client_product_rate"),)
    # Note: this constraint does NOT prevent two client-wide rows
    # (product_id=NULL) for the same client - SQL treats NULL as
    # distinct from NULL in a unique constraint. The create route
    # enforces "at most one client-wide default per client" at the
    # application level instead.

    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    # Nullable: a row with product_id=None is a CLIENT-WIDE default
    # margin (e.g. "Meenal gets 15% on everything"), distinct from a
    # row with a specific product_id, which overrides just that one
    # product for that one client. The resolution lookup checks the
    # specific-product row first, then falls back to the client-wide
    # row - see client_product_rates.py's resolve_pricing.
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)

    margin_percent = Column(Numeric(5, 2), nullable=True)  # customer-specific margin override
    fixed_selling_price = Column(Numeric(12, 2), nullable=True)  # direct negotiated price override

    notes = Column(Text, nullable=True)
    created_by = Column(String(255), nullable=True)

    client = relationship("Client")
    product = relationship("Product")
