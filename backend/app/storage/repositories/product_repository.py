from typing import Any, Dict, List

from app.storage.base_repository import BaseRepository
from app.utils.product_import import VALID_PRODUCT_TYPES


class ProductRepository(BaseRepository):
    """Mirrors ProductBase (app/schemas/product.py): name and unit are
    required (unit defaults to "Nos" if omitted, matching the schema's
    own default). product_type must be "standard" or "custom" - reused
    from product_import.py's VALID_PRODUCT_TYPES rather than
    redeclared here, so the two paths can never quietly drift apart."""
    collection_name = "products"

    def validate(self, data: Dict[str, Any]) -> List[str]:
        errors = []
        name = data.get("name")
        if not name or not str(name).strip():
            errors.append("Product name is required")

        product_type = data.get("product_type", "standard")
        if product_type not in VALID_PRODUCT_TYPES:
            errors.append(f"Type must be 'standard' or 'custom' (got {product_type!r})")

        return errors
