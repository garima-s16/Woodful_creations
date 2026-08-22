"""Excel import for the Client Master (Family 101/21 - Client Master
section 17). Same discipline as app/utils/product_import.py /
purchase_import.py: one fixed template shared by the download and the
parser, phone/GSTIN/email validated with the exact same rules the API
enforces (so an import can't create a client the API itself would have
rejected), never writes a parsed row directly to the database -
preview and commit are two separate steps, and uploaded Client IDs are
never trusted (the column doesn't even exist in the template - IDs are
always server-generated, per Client Master section 2/17).
"""
import re
from io import BytesIO
from typing import List, Optional

import openpyxl
from openpyxl import Workbook

from app.utils.exporters import write_sheet, write_instructions_sheet, add_dropdown_validation
from app.utils.validators import validate_phone, validate_email
from app.utils.client_matching import normalize_name, normalize_phone
from app.schemas.client import CLIENT_TYPES

TEMPLATE_VERSION = "2.0"  # bumped from 1.0: adds Client Type (mandatory), State, Pincode - Family 103 section 9

# Data-sheet headers use the section-4 "*" convention for mandatory fields.
# Internal/canonical names (used by HEADER_ALIASES, parsing, and the
# preview/commit schemas) stay asterisk-free; only the printed header differs.
CLIENT_IMPORT_COLUMNS = [
    "Client Name *", "Client Type *", "Contact Person", "Phone *", "Alternate Phone", "Email",
    "Address", "Site Address", "City", "State", "Pincode", "GSTIN", "Lead Source", "Notes",
]

HEADER_ALIASES = {
    "client": "Client Name *",
    "client name": "Client Name *",
    "name": "Client Name *",
    "client type": "Client Type *",
    "type": "Client Type *",
    "contact person": "Contact Person",
    "contact": "Contact Person",
    "phone": "Phone *",
    "phone number": "Phone *",
    "mobile": "Phone *",
    "alternate phone": "Alternate Phone",
    "alt phone": "Alternate Phone",
    "email": "Email",
    "address": "Address",
    "billing address": "Address",
    "site address": "Site Address",
    "city": "City",
    "state": "State",
    "pincode": "Pincode",
    "pin code": "Pincode",
    "zip": "Pincode",
    "gstin": "GSTIN",
    "lead source": "Lead Source",
    "source": "Lead Source",
    "notes": "Notes",
    "remarks": "Notes",
}
for _col in CLIENT_IMPORT_COLUMNS:
    HEADER_ALIASES.setdefault(_col.lower(), _col)
    HEADER_ALIASES.setdefault(_col.rstrip(" *").lower(), _col)

# Alternate Phone is accepted but not required - a client may only have
# one number on file, which is fine, as long as the primary Phone is set.
REQUIRED_COLUMNS = ["Client Name *", "Client Type *", "Phone *"]


def _normalize_header_cell(raw) -> Optional[str]:
    if raw is None:
        return None
    key = re.sub(r"\s+", " ", str(raw).strip().lower())
    return HEADER_ALIASES.get(key)


def _resolve_header_row(values) -> Optional[dict]:
    resolved = {}
    for idx, raw in enumerate(values):
        canonical = _normalize_header_cell(raw)
        if canonical is None:
            continue
        if canonical in resolved:
            return None
        resolved[canonical] = idx
    if all(col in resolved for col in REQUIRED_COLUMNS):
        return resolved
    return None


def normalize_match_key(name: Optional[str], phone: Optional[str]) -> str:
    """A client is treated as a match ONLY if BOTH name and phone match
    an existing client - this is the same Client Recognition rule used
    for order intake (see app/utils/client_matching.py), reused here
    rather than re-implemented, so the two entry points can never
    silently drift apart on what "matches" means. Name alone is too
    common (multiple "Ravi"s are plausible); phone alone could be a
    shared family/office line; both together is the confirmed rule."""
    return f"{normalize_name(name)}|{normalize_phone(phone)}"


# Approved Woodful demo data (Family 103 sections 3 & 10) - real Woodful
# sample client names, never generic "Test/Demo/Reference" placeholders.
# Two rows here so both Client Types (Individual/Business) are demonstrated
# in place, since Client Type is a new mandatory field.
EXAMPLE_ROWS = [
    {
        "Client Name *": "Sanket", "Client Type *": "Individual", "Contact Person": "", "Phone *": "9812345670",
        "Alternate Phone": "", "Email": "sanket@example.com", "Address": "123 Vijay Nagar, Indore",
        "Site Address": "Same as address", "City": "Indore", "State": "Madhya Pradesh", "Pincode": "452010",
        "GSTIN": "", "Lead Source": "Referral", "Notes": "Sample row - delete before uploading your real data",
    },
    {
        "Client Name *": "Meenal Interiors Pvt Ltd", "Client Type *": "Business", "Contact Person": "Meenal",
        "Phone *": "9823456781", "Alternate Phone": "9834567892", "Email": "meenal@example.com",
        "Address": "456 Race Course Road, Indore", "Site Address": "789 AB Road, Indore",
        "City": "Indore", "State": "Madhya Pradesh", "Pincode": "452001", "GSTIN": "23ABCDE1234F1Z5",
        "Lead Source": "Architect", "Notes": "Sample row with GSTIN - delete before uploading your real data",
    },
]

CLIENT_FIELD_DOCS = [
    {"name": "Client Name *", "mandatory": True, "meaning": "Full name of the client or company.",
     "format": "Free text."},
    {"name": "Client Type *", "mandatory": True, "meaning": "Whether the client is a person or a company.",
     "format": "Must match exactly.", "accepted_values": list(CLIENT_TYPES)},
    {"name": "Contact Person", "mandatory": False,
     "meaning": "Who to actually call, when the client is a company or family rather than a single individual.",
     "format": "Free text."},
    {"name": "Phone *", "mandatory": True, "meaning": "Primary contact number.",
     "format": "Exactly 10 digits, no country code or separators."},
    {"name": "Alternate Phone", "mandatory": False, "meaning": "A second contact number, if any.",
     "format": "10 digits."},
    {"name": "Email", "mandatory": False, "meaning": "Contact email.", "format": "Valid email address."},
    {"name": "Address", "mandatory": False, "meaning": "Billing address.", "format": "Free text."},
    {"name": "Site Address", "mandatory": False,
     "meaning": "Where the work actually happens, if different from the billing address.", "format": "Free text."},
    {"name": "City", "mandatory": False, "meaning": "City.", "format": "Free text."},
    {"name": "State", "mandatory": False, "meaning": "State.", "format": "Free text."},
    {"name": "Pincode", "mandatory": False, "meaning": "Postal code.", "format": "Up to 10 digits."},
    {"name": "GSTIN", "mandatory": False, "meaning": "GST registration number, if the client has one.",
     "format": "Exactly 15 characters."},
    {"name": "Lead Source", "mandatory": False, "meaning": "How this client found Woodful.",
     "format": "Free text - use the same values as the Client form's Lead Source list."},
    {"name": "Notes", "mandatory": False, "meaning": "Any other remarks about the client.", "format": "Free text."},
]


def build_import_template() -> BytesIO:
    wb = Workbook()
    wb.remove(wb.active)
    ws = write_sheet(
        wb, sheet_name="Clients", title="Woodful Creations - Client Import Template",
        subtitle="Client Name, Client Type, and Phone are required for every row (marked with *). "
                  "Client ID is generated automatically - do not add a Client ID column. "
                  "Do not change the column headers.",
        columns=CLIENT_IMPORT_COLUMNS, rows=EXAMPLE_ROWS,
    )
    type_col_letter = chr(ord("A") + CLIENT_IMPORT_COLUMNS.index("Client Type *"))
    add_dropdown_validation(ws, type_col_letter, CLIENT_TYPES, first_row=ws.woodful_header_row + 1)

    write_instructions_sheet(
        wb, template_name="Woodful Clients Import Template", version=TEMPLATE_VERSION,
        field_docs=CLIENT_FIELD_DOCS,
        id_rule="Client ID is system-generated and never typed in by hand. Leave any ID column out entirely - "
                "there is none in this template.",
        duplicate_rule="A row is only treated as an existing client if BOTH Client Name and Phone match an "
                        "existing client exactly - it will be reused, not re-created. A row whose name closely "
                        "resembles (but doesn't exactly match) an existing client is flagged as a possible match "
                        "during preview; you will be asked to confirm whether to use the existing client or create "
                        "a new one. Nothing is merged or created automatically on a possible match.",
        extra_notes=[
            "A completely blank row is skipped. A row with only some fields filled in is still validated - "
            "if Client Name, Client Type, or Phone is missing, that row will show an error.",
            "This template does not use a Client ID column. An existing client is recognized only when both "
            "Client Name and Phone match exactly (see Duplicate / Typo Handling above).",
        ],
    )
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def _clean(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value if value else None
    if isinstance(value, (int, float)):
        # A phone/GSTIN typed into Excel can get read back as a number
        # (e.g. Excel auto-formats a bare digit string) - stringify it
        # rather than silently dropping it as an invalid type.
        return str(int(value)) if float(value).is_integer() else str(value)
    return value


def parse_uploaded_workbook(file_bytes: bytes) -> List[dict]:
    wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True)
    ws = wb.worksheets[0]

    header_row_idx = None
    col_index = None
    for row in ws.iter_rows(min_row=1, max_row=10):
        values = [c.value for c in row]
        resolved = _resolve_header_row(values)
        if resolved:
            header_row_idx = row[0].row
            col_index = resolved
            break
    if header_row_idx is None:
        raise ValueError(
            "Couldn't find the expected column headers in this file. "
            "Please use the downloaded template, or make sure Client Name and Phone "
            "have a recognizable header and aren't duplicated."
        )

    rows = []
    for row in ws.iter_rows(min_row=header_row_idx + 1):
        values = [c.value for c in row]
        if all(_clean(v) is None for v in values):
            continue
        rows.append({name: _clean(values[idx]) if idx < len(values) else None for name, idx in col_index.items()})
    return rows


def validate_and_match_row(row: dict, existing_by_key: dict, fuzzy_candidates: Optional[list] = None):
    """Validates one parsed row with the exact same rules the Client
    API enforces (validate_phone/validate_email/15-char GSTIN), and
    checks whether it looks like a duplicate of an existing client -
    both an exact (name+phone) match and, when fuzzy_candidates is
    supplied, a "possible match" typo/near-match nudge (Family 103
    section 8), using the same shared logic as the UI's check-duplicates
    endpoint (see app.utils.client_matching.find_fuzzy_name_matches).
    Returns (result_dict, errors_list); never writes anything."""
    errors = []
    name = row.get("Client Name *")
    if not name:
        errors.append("Client Name is required")

    raw_client_type = row.get("Client Type *")
    client_type = str(raw_client_type).strip() if raw_client_type else raw_client_type
    if not client_type:
        errors.append("Client Type is required")
    elif client_type not in CLIENT_TYPES:
        errors.append(f"Client Type must be one of: {', '.join(CLIENT_TYPES)} (got {client_type!r})")

    phone = row.get("Phone *")
    if not phone or not validate_phone(str(phone).strip()):
        errors.append("Please enter valid mobile number")

    email = row.get("Email")
    if email and not validate_email(email):
        errors.append(f"Invalid email: {email!r}")

    gstin = row.get("GSTIN")
    if gstin and len(gstin) != 15:
        errors.append(f"GSTIN must contain 15 characters (got {len(gstin)}): {gstin!r}")

    matched = existing_by_key.get(normalize_match_key(name, phone)) if name and phone else None

    possible_match = None
    if not matched and name and fuzzy_candidates is not None:
        from app.utils.client_matching import find_fuzzy_name_matches
        fuzzy_hits = find_fuzzy_name_matches(db=None, name=name, candidates=fuzzy_candidates, limit=1)
        possible_match = fuzzy_hits[0] if fuzzy_hits else None

    result = {
        "name": name, "client_type": client_type, "contact_person": row.get("Contact Person"), "phone": phone,
        "alternate_phone": row.get("Alternate Phone"), "email": email, "address": row.get("Address"),
        "site_address": row.get("Site Address"), "city": row.get("City"), "state": row.get("State"),
        "pincode": row.get("Pincode"), "gstin": gstin,
        "lead_source": row.get("Lead Source"), "remarks": row.get("Notes"),
        "matched_client_id": matched.id if matched else None,
        "is_duplicate": matched is not None,
        "possible_match_client_id": possible_match.id if possible_match else None,
        "possible_match_name": possible_match.name if possible_match else None,
    }
    return result, errors
