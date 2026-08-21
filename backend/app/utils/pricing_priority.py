"""Pricing priority resolution (customer-specific pricing).

Implements the exact priority order from the spec:

    1. Explicit line-item selling-price override
    2. Customer-specific product/rate override (fixed price)
    3. Customer-specific margin
    4. Estimate-specific margin
    5. Product-specific configured margin
    6. Global/default margin

"Do not silently combine conflicting overrides" - resolve_selling_rate
always returns which single rule actually won, not a blend of several.
Every caller (Estimate creation, a future Order-direct-pricing UI) goes
through this one function so the priority order can never be
re-implemented slightly differently in two places.
"""
from decimal import Decimal
from typing import Optional, NamedTuple

from app.utils.pricing_engine import compute_selling_rate

# Woodful's system-wide fallback when nothing more specific is
# configured anywhere (priority level 6). This is deliberately the
# only hardcoded number in this module - everything above it comes
# from real, editable data (Product, ClientProductRate, Estimate,
# explicit override).
DEFAULT_MARGIN_PERCENT = Decimal("30")

PRICING_RULES = (
    "EXPLICIT_LINE_ITEM_OVERRIDE",
    "CUSTOMER_PRODUCT_PRICE_OVERRIDE",
    "CUSTOMER_MARGIN_OVERRIDE",
    "ESTIMATE_MARGIN_OVERRIDE",
    "PRODUCT_MARGIN",
    "GLOBAL_DEFAULT_MARGIN",
)


class ResolvedPrice(NamedTuple):
    selling_rate: Decimal
    pricing_rule_applied: str  # one of PRICING_RULES - shown in the UI, never hidden
    margin_percent_used: Optional[Decimal]  # None when a fixed price override was used (no margin math involved)


def resolve_selling_rate(
    cost: Decimal,
    explicit_override: Optional[Decimal] = None,
    customer_product_fixed_price: Optional[Decimal] = None,
    customer_margin_percent: Optional[Decimal] = None,
    estimate_margin_percent: Optional[Decimal] = None,
    product_margin_percent: Optional[Decimal] = None,
) -> ResolvedPrice:
    """Walks the six priority levels in order, stopping at the first
    one that's actually set. cost is only used once margin math is
    reached (levels 3-6) - a fixed price override (levels 1-2) is
    returned as-is regardless of cost, since it isn't derived from cost
    at all.
    """
    if explicit_override is not None:
        return ResolvedPrice(explicit_override, "EXPLICIT_LINE_ITEM_OVERRIDE", None)
    if customer_product_fixed_price is not None:
        return ResolvedPrice(customer_product_fixed_price, "CUSTOMER_PRODUCT_PRICE_OVERRIDE", None)
    if customer_margin_percent is not None:
        return ResolvedPrice(compute_selling_rate(cost, customer_margin_percent),
                              "CUSTOMER_MARGIN_OVERRIDE", customer_margin_percent)
    if estimate_margin_percent is not None:
        return ResolvedPrice(compute_selling_rate(cost, estimate_margin_percent),
                              "ESTIMATE_MARGIN_OVERRIDE", estimate_margin_percent)
    if product_margin_percent is not None:
        return ResolvedPrice(compute_selling_rate(cost, product_margin_percent),
                              "PRODUCT_MARGIN", product_margin_percent)
    return ResolvedPrice(compute_selling_rate(cost, DEFAULT_MARGIN_PERCENT),
                          "GLOBAL_DEFAULT_MARGIN", DEFAULT_MARGIN_PERCENT)
