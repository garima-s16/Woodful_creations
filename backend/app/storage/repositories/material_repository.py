from typing import Any, Dict, List

from app.storage.base_repository import BaseRepository


class MaterialRepository(BaseRepository):
    """Mirrors MaterialBase (app/schemas/material.py): name and unit
    are the only hard requirements at the schema level - everything
    else (category, subcategory_id, brand_grade, stock levels,
    supplier_id, location) is genuinely optional there too."""
    collection_name = "materials"

    def validate(self, data: Dict[str, Any]) -> List[str]:
        errors = []
        if not data.get("name") or not str(data.get("name")).strip():
            errors.append("Material name is required")
        if not data.get("unit"):
            errors.append("Unit is required")
        return errors
