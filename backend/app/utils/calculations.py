"""Centralized discount/GST calculation - Family 102 section 2/7:
"Calculations must be performed server-side... The backend must
recalculate: Line Total, Subtotal, Discount, Tax, Grand Total before
saving." Originally only implemented for Estimates; Orders had no
discount/tax fields at all (order_value was just a raw sum of line
items). Both now share this one implementation rather than risk the
two formulas drifting apart.
"""
from decimal import Decimal, ROUND_HALF_UP


def compute_totals(subtotal: Decimal, discount: Decimal, tax_percent: Decimal):
    """discount is an absolute currency amount (not a percentage) -
    matching the existing Estimate.discount field's established
    meaning; a caller wanting "10% off" computes the amount itself
    (subtotal * 10 / 100) before calling this, the same way the
    existing Estimate creation flow always has.

    taxable = subtotal - discount; tax is applied to the taxable
    amount, not the raw subtotal. Returns (tax_amount, grand_total).
    """
    taxable = subtotal - discount
    if taxable < 0:
        taxable = Decimal("0")
    tax_amount = (taxable * tax_percent / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return tax_amount, taxable + tax_amount
