from app.core.constants import MATERIAL_TYPES
from app.core.exceptions import InvalidMaterialError, InvalidThicknessError

def validate_material_thickness(material_type: str, thickness: float) -> bool:
    if material_type not in MATERIAL_TYPES:
        raise InvalidMaterialError(material_type)
    
    valid_thicknesses = MATERIAL_TYPES[material_type]
    if thickness not in valid_thicknesses:
        raise InvalidThicknessError(material_type, thickness)
    
    return True

def validate_email(email: str) -> bool:
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone: str) -> bool:
    import re
    pattern = r'^[+]?[0-9]{10,}$'
    return re.match(pattern, phone) is not None

def validate_username(username: str) -> bool:
    if len(username) < 3 or len(username) > 50:
        return False
    return username.isalnum() or '_' in username

def validate_password_strength(password: str) -> tuple[bool, str]:
    errors = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters")
    if not any(c.isupper() for c in password):
        errors.append("Password must contain uppercase letter")
    if not any(c.islower() for c in password):
        errors.append("Password must contain lowercase letter")
    if not any(c.isdigit() for c in password):
        errors.append("Password must contain digit")
    if not any(c in '!@#$%^&*' for c in password):
        errors.append("Password must contain special character")
    
    return len(errors) == 0, "; ".join(errors) if errors else ""