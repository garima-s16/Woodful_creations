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


def compute_total_cost(
    material_cost: Decimal = Decimal("0"),
    hardware_cost: Decimal = Decimal("0"),
    consumables_cost: Decimal = Decimal("0"),
    labour_cost: Decimal = Decimal("0"),
    machine_cost: Decimal = Decimal("0"),
    design_cost: Decimal = Decimal("0"),
    finishing_cost: Decimal = Decimal("0"),
    packaging_cost: Decimal = Decimal("0"),
    transport_cost: Decimal = Decimal("0"),
    installation_cost: Decimal = Decimal("0"),
    job_work_cost: Decimal = Decimal("0"),
    wastage_percent: Decimal = Decimal("0"),
    overhead_percent: Decimal = Decimal("0"),
) -> dict:
    """Material + Hardware + Consumables + Labour + Machine + Design/CAD
    + Finishing + Packaging + Transport + Installation + Job Work =
    direct cost. Wastage% and Overhead% are both applied on top of
    direct cost (not compounded on each other), matching the spec's
    "Direct Cost + Wastage + Applicable Overhead" ordering. Returns
    every intermediate figure, not just the total, so a UI/PDF can show
    the full breakdown rather than one opaque number.
    """
    direct_cost = (
        material_cost + hardware_cost + consumables_cost + labour_cost + machine_cost
        + design_cost + finishing_cost + packaging_cost + transport_cost
        + installation_cost + job_work_cost
    )
    wastage_amount = (direct_cost * wastage_percent / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    overhead_amount = (direct_cost * overhead_percent / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total_cost = direct_cost + wastage_amount + overhead_amount
    return {
        "direct_cost": direct_cost,
        "wastage_amount": wastage_amount,
        "overhead_amount": overhead_amount,
        "total_internal_cost": total_cost,
    }


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


def compute_customer_total(selling_rate: Decimal, tax_percent: Decimal) -> dict:
    """Selling Rate + Tax = Customer Total. Separate step from margin
    calculation - tax is never blended into the margin math, matching
    the spec's explicit ordering (margin first, then tax)."""
    tax_amount = (selling_rate * tax_percent / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"tax_amount": tax_amount, "customer_total": selling_rate + tax_amount}


def compute_full_pricing(cost_components: dict, wastage_percent: Decimal, overhead_percent: Decimal,
                          target_margin_percent: Decimal, tax_percent: Decimal) -> dict:
    """End-to-end: cost components -> total internal cost -> selling
    rate -> customer total. Returns every layer so the UI can display
    "Market Reference / Woodful Cost / Woodful Selling Rate" as three
    genuinely distinct numbers, per the spec's explicit requirement
    that these never be shown as interchangeable."""
    cost_breakdown = compute_total_cost(wastage_percent=wastage_percent, overhead_percent=overhead_percent, **cost_components)
    selling_rate = compute_selling_rate(cost_breakdown["total_internal_cost"], target_margin_percent)
    tax_breakdown = compute_customer_total(selling_rate, tax_percent)
    return {**cost_breakdown, "woodful_selling_rate": selling_rate, **tax_breakdown}
