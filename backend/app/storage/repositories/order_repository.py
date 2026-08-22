from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List

from app.storage.base_repository import BaseRepository
from app.utils.quantity_rules import quantity_violates_whole_unit_rule


class OrderRepository(BaseRepository):
    """Mirrors the real Order model/schema: client_id required, and
    the same whole-number-quantity check OrderItemCreate's own
    model_validator enforces, reused from the same shared module
    EstimateRepository uses - Estimate and Order line items follow
    identical quantity rules in the real API, and this keeps that true
    here too."""
    collection_name = "orders"

    def validate(self, data: Dict[str, Any]) -> List[str]:
        errors = []
        if data.get("client_id") is None:
            errors.append("client_id is required")

        for i, item in enumerate(data.get("items", []), start=1):
            quantity = item.get("quantity")
            unit = item.get("unit")
            if quantity is None or unit is None:
                continue
            try:
                quantity = Decimal(str(quantity))
            except InvalidOperation:
                errors.append(f"Item {i}: invalid quantity {item.get('quantity')!r}")
                continue
            if quantity_violates_whole_unit_rule(quantity, unit):
                errors.append(f"Item {i}: {unit} must be a whole number, not a fractional quantity.")

        return errors
