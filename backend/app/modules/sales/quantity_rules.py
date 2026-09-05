"""Countable-unit quantity validation - genuinely shared logic, not
duplicated. Used by app/modules/sales/schemas.py (re-exported from there for
existing importers) and directly by both app/modules/sales/imports/estimate_import.py
and app/modules/sales/imports/order_import.py - kept as its own module so all three
genuinely share one function rather than risk copies quietly drifting
apart.
"""
from decimal import Decimal

# Countable units - a finished piece of furniture (or any other
# discretely-counted item) doesn't come in fractional units. A
# measurable/continuous unit genuinely can. Matched case-insensitively
# against whatever's typed/selected in the Unit field.
WHOLE_NUMBER_UNITS = {
    "piece", "pieces", "pcs", "pc", "set", "sets", "pair", "pairs",
    "nos", "no", "box", "boxes", "roll", "rolls", "bundle", "bundles",
    "sheet", "sheets", "job", "jobs",
}


def quantity_violates_whole_unit_rule(quantity: Decimal, unit) -> bool:
    if not unit or unit.strip().lower() not in WHOLE_NUMBER_UNITS:
        return False
    return quantity != quantity.to_integral_value()
