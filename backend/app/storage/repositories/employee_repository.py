from typing import Any, Dict, List

from app.storage.base_repository import BaseRepository
from app.utils.validators import validate_phone


class EmployeeRepository(BaseRepository):
    """Mirrors EmployeeBase (app/schemas/employee.py): name is
    required; phone is optional but must be exactly 10 digits if
    given, same rule and message as Client/Supplier."""
    collection_name = "employees"

    def validate(self, data: Dict[str, Any]) -> List[str]:
        errors = []
        if not data.get("name") or not str(data.get("name")).strip():
            errors.append("Employee name is required")

        phone = data.get("phone")
        if phone and not validate_phone(phone):
            errors.append("Please enter valid mobile number")

        return errors
