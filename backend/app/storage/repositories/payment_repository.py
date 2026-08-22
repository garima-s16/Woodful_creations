from typing import Any, Dict, List

from app.storage.base_repository import BaseRepository


class PaymentRepository(BaseRepository):
    """Mirrors PaymentBase (app/schemas/payment.py): date, order_id,
    payment_type, payment_mode, and amount are all genuinely required
    there (no defaults) - a Payment record isn't meaningful without
    all five."""
    collection_name = "payments"

    def validate(self, data: Dict[str, Any]) -> List[str]:
        errors = []
        for field in ("date", "order_id", "payment_type", "payment_mode", "amount"):
            if data.get(field) is None:
                errors.append(f"{field} is required")
        return errors
