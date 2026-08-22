from typing import Any, Dict, List

from app.storage.base_repository import BaseRepository
from app.utils.validators import validate_phone


class SupplierRepository(BaseRepository):
    """Mirrors SupplierBase's actual validation (app/schemas/supplier.py):
    name is required, phone is OPTIONAL but must be exactly 10 digits
    if given (unlike Client, where phone is mandatory), gstin must be
    exactly 15 characters if given."""
    collection_name = "suppliers"

    def validate(self, data: Dict[str, Any]) -> List[str]:
        errors = []
        name = data.get("name")
        if not name or not str(name).strip():
            errors.append("Supplier name is required")

        phone = data.get("phone")
        if phone and not validate_phone(phone):
            errors.append("Please enter valid mobile number")

        gstin = data.get("gstin")
        if gstin and len(gstin) != 15:
            errors.append("GSTIN must contain 15 characters.")

        return errors
