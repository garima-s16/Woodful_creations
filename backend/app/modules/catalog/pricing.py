"""Catalog pricing: selling-rate computation and priority-based
rate-source resolution. Combines the former pricing_engine.py and
pricing_priority.py."""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, NamedTuple


# --- pricing_engine.py ---
"""Pricing calculation engine (Rate Master).

Implements the cost engine and the Woodful Selling Rate formula exactly
as specified - this is the one place that formula lives, so an
Estimate/Order/RateCard can never each compute margin slightly
differently and drift apart.

CRITICAL correctness note (explicitly called out in the spec, and the
easiest thing to get wrong): margin is GROSS MARGIN on the selling
price, not a markup on cost. These are different numbers:

    Cost = Rs 100, target margin = 30%
    Markup formula (WRONG):  100 * 1.30 = Rs 130
    Margin formula (RIGHT):  100 / (1 - 0.30) = Rs 142.86

A 30% *margin* means 30% of the final selling price is profit - if you
sell at Rs 130, profit is 30/130 = 23.1%, not 30%. Only dividing by
(1 - margin%) actually yields a selling price where margin% of that
price is profit.
"""

def compute_selling_rate(total_cost: Decimal, target_margin_percent: Decimal) -> Decimal:
    """Selling Price = Cost / (1 - Margin%) - see module docstring for
    why this is margin, not markup. target_margin_percent must be a
    percentage below 100 (100% margin is mathematically undefined -
    it would require an infinite selling price); this function does not
    clamp or silently correct an out-of-range value, it's the caller's
    (schema validator's) job to reject that before this ever runs.
    """
    margin_fraction = target_margin_percent / Decimal("100")
    denominator = Decimal("1") - margin_fraction
    if denominator <= 0:
        raise ValueError("Target margin must be less than 100%.")
    selling_rate = (total_cost / denominator).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return selling_rate


# --- pricing_priority.py ---
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

DEFAULT_MARGIN_PERCENT = Decimal("30")


PRICING_RULES = (
    "EXPLICIT_LINE_ITEM_OVERRIDE",
    "CUSTOMER_PRODUCT_PRICE_OVERRIDE",
    "CUSTOMER_MARGIN_OVERRIDE",
    "ESTIMATE_MARGIN_OVERRIDE",
    "PRODUCT_MARGIN",
    "GLOBAL_DEFAULT_MARGIN",
    # Not returned by resolve_selling_rate itself - used by
    # clients/api.py's resolve_pricing when no cost basis exists at all
    # (cost is missing/unknown, not legitimately zero) and no fixed-
    # price override applies either. Falls back to the product's own
    # stored selling_price rather than inventing a cost of 0 and
    # running margin math against it.
    "PRODUCT_STORED_SELLING_PRICE",
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


class PricingSnapshot(NamedTuple):
    pricing_rule_applied: Optional[str]  # None only when no rule could be determined at all (no cost, no stored price)
    applied_margin_percent: Optional[Decimal]
    cost_at_creation: Optional[Decimal]  # None = cost unknown, never a fabricated 0 (see resolve_selling_rate's caller in clients/api.py)


def resolve_product_pricing_snapshot(db, product, client_id: Optional[int] = None,
                                      estimate_margin_percent: Optional[Decimal] = None) -> PricingSnapshot:
    """Single shared entry point for 'which pricing rule/margin/cost
    basis is currently in effect for this product+client(+estimate)' -
    used by estimate line-item creation and import (sales/api.py) to
    populate EstimateLineItem's historical pricing snapshot fields, so
    that logic is never re-implemented separately from the equivalent
    resolution clients/api.py's resolve_pricing preview endpoint does.

    This does NOT decide the line item's actual rate/amount charged -
    those remain whatever was supplied (typed or imported) - it only
    determines what to record as the pricing DECISION context behind
    that rate, exactly as EstimateLineItem.pricing_rule_applied's own
    docstring describes.

    cost is resolved the same "is not None" way as sales/api.py's
    existing cost_at_creation logic - a legitimately-zero cost_price is
    never confused with a missing one. When no cost basis exists at
    all AND no customer-specific fixed price applies, this falls back
    to the product's own stored selling_price (PRODUCT_STORED_SELLING_PRICE)
    rather than inventing a cost of 0, same fix as clients/api.py's
    resolve_pricing (item 14's fix) - not duplicated logic, the same
    reasoning applied at the one other place a cost basis is resolved
    for pricing."""
    from app.modules.clients.models import ClientProductRate

    cost_basis = product.cost_price if product.cost_price is not None else product.suggested_cost_price
    cost_known = cost_basis is not None
    cost = Decimal(str(cost_basis)) if cost_known else Decimal("0")

    customer_fixed = None
    customer_margin = None
    if client_id:
        override = db.query(ClientProductRate).filter(
            ClientProductRate.client_id == client_id, ClientProductRate.product_id == product.id,
        ).first()
        if not override:
            override = db.query(ClientProductRate).filter(
                ClientProductRate.client_id == client_id, ClientProductRate.product_id.is_(None),
            ).first()
        if override:
            customer_fixed = override.fixed_selling_price
            customer_margin = override.margin_percent

    would_use_margin_math = customer_fixed is None
    if not cost_known and would_use_margin_math:
        if product.selling_price is not None:
            return PricingSnapshot(
                pricing_rule_applied="PRODUCT_STORED_SELLING_PRICE", applied_margin_percent=None, cost_at_creation=None,
            )
        # No cost basis and no stored selling price either - genuinely
        # nothing to record. Left None/unknown rather than guessed,
        # same convention as cost_at_creation itself for pre-existing
        # rows (see EstimateLineItem.cost_at_creation's docstring).
        return PricingSnapshot(pricing_rule_applied=None, applied_margin_percent=None, cost_at_creation=None)

    result = resolve_selling_rate(
        cost=cost, customer_product_fixed_price=customer_fixed, customer_margin_percent=customer_margin,
        estimate_margin_percent=estimate_margin_percent, product_margin_percent=product.margin_percent,
    )
    return PricingSnapshot(
        pricing_rule_applied=result.pricing_rule_applied, applied_margin_percent=result.margin_percent_used,
        cost_at_creation=cost if cost_known else None,
    )
