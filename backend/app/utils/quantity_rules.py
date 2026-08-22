"""Countable-unit quantity validation - genuinely shared logic, not
duplicated. Originally lived only in app/schemas/estimate.py, but that
module imports pydantic, which the storage abstraction layer
(app/storage/) must NOT depend on - a repository needs to be
importable and testable in an environment that may not have pydantic
(or any other API-layer dependency) installed at all. Extracted here
so both app/schemas/estimate.py and app/storage/repositories/ import
the exact same function rather than risk two copies quietly drifting
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
