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
from decimal import Decimal, ROUND_HALF_UP


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
