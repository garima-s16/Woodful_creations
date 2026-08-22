from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List

from app.storage.base_repository import BaseRepository
from app.utils.quantity_rules import quantity_violates_whole_unit_rule


class EstimateRepository(BaseRepository):
    """Mirrors EstimateBase (app/schemas/estimate.py): client_id is a
    required int (unlike most other Optional fields on this schema).
    Each line item, if present, gets the same whole-number-quantity
    check the real API enforces (app/schemas/estimate.py's
    quantity_violates_whole_unit_rule, added when the G2 bug - '1.23
    sofa' being silently accepted - was fixed) - reused directly here
    rather than reimplemented, so the two paths can never disagree
    about what counts as valid."""
    collection_name = "estimates"

    def validate(self, data: Dict[str, Any]) -> List[str]:
        errors = []
        client_id = data.get("client_id")
        if client_id is None:
            errors.append("client_id is required")

        for i, item in enumerate(data.get("line_items", []), start=1):
            quantity = item.get("quantity")
            unit = item.get("unit")
            if quantity is None or unit is None:
                continue
            try:
                quantity = Decimal(str(quantity))
            except InvalidOperation:
                errors.append(f"Line item {i}: invalid quantity {item.get('quantity')!r}")
                continue
            if quantity_violates_whole_unit_rule(quantity, unit):
                errors.append(f"Line item {i}: {unit} must be a whole number, not a fractional quantity.")

        return errors
