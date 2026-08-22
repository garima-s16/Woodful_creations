"""Concrete example: ClientRepository. This is the one entity fully
wired through the new storage abstraction and genuinely tested end to
end (see the test file for real create/read/update/list/delete cycles
run against LocalJSONStorageProvider). The other ~48 model types
listed in Section 1 (Suppliers, Products, Materials, Employees,
Estimates, Orders, Payments, ...) are NOT yet built - this one
repository exists to prove the pattern works before mechanically
repeating it across every entity, and to give a concrete template for
that repeat.
"""
from typing import Any, Dict, List

from app.storage.base_repository import BaseRepository
from app.utils.validators import validate_phone, validate_email


class ClientRepository(BaseRepository):
    collection_name = "clients"

    def validate(self, data: Dict[str, Any]) -> List[str]:
        errors = []
        name = data.get("name")
        if not name or not str(name).strip():
            errors.append("Client name is required")

        phone = data.get("phone")
        if not phone:
            errors.append("Please enter valid mobile number")
        elif not validate_phone(phone):
            errors.append("Please enter valid mobile number")

        email = data.get("email")
        if email and not validate_email(email):
            errors.append("Please enter a valid email address")

        return errors
