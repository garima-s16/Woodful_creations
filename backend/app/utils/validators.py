def validate_email(email: str) -> bool:
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone: str) -> bool:
    """Mandatory rule: a mobile number must be exactly 10 digits - no
    country code prefix, no more, no less. Matches the Indian mobile
    number convention Woodful's own business data uses throughout.
    Callers should show 'Please enter valid mobile number' when this
    returns False (the exact wording used on both the client form and
    the Excel import error report).
    """
    import re
    pattern = r'^[0-9]{10}$'
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


# ---------------------------------------------------------------------------
# File-signature ("magic bytes") sniffing, used alongside the existing
# extension + Content-Type allowlists on every upload endpoint. Extension and
# Content-Type are both attacker-controlled (a renamed .exe with a spoofed
# header still passes those two checks) - this looks at the actual leading
# bytes of the file to confirm the content matches what the extension claims.
# Deliberately small and dependency-free rather than pulling in a new library.
# ---------------------------------------------------------------------------

# ext -> one or more acceptable "families" of magic-byte signatures.
# PDF, JPEG, PNG have single well-known signatures. DOC (legacy OLE) has one
# signature. DOCX/XLSX are both ZIP containers (PK\x03\x04 or the empty-zip
# variant PK\x05\x06), so both map to the same "zip" family.
_FILE_SIGNATURES = {
    "pdf": [b"%PDF-"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "doc": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],  # legacy OLE compound file
    "docx": [b"PK\x03\x04", b"PK\x05\x06"],
    "xlsx": [b"PK\x03\x04", b"PK\x05\x06"],
}


def validate_file_signature(ext: str, header: bytes) -> bool:
    """Returns True if `header` (the first bytes read from the uploaded
    file) matches a known-good magic-byte signature for the claimed
    extension `ext`. Extensions with no signature registered (there are
    none currently expected to reach this function) fail closed."""
    signatures = _FILE_SIGNATURES.get(ext.lower())
    if not signatures:
        return False
    return any(header.startswith(sig) for sig in signatures)