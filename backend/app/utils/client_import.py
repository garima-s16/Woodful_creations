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

from app.utils.exporters import write_sheet
from app.utils.validators import validate_phone, validate_email
from app.utils.client_matching import normalize_name, normalize_phone

CLIENT_IMPORT_COLUMNS = [
    "Client Name", "Contact Person", "Phone", "Alternate Phone", "Email",
    "Address", "Site Address", "City", "GSTIN", "Lead Source", "Notes",
]

HEADER_ALIASES = {
    "client": "Client Name",
    "client name": "Client Name",
    "name": "Client Name",
    "contact person": "Contact Person",
    "contact": "Contact Person",
    "phone": "Phone",
    "phone number": "Phone",
    "mobile": "Phone",
    "alternate phone": "Alternate Phone",
    "alt phone": "Alternate Phone",
    "email": "Email",
    "address": "Address",
    "billing address": "Address",
    "site address": "Site Address",
    "city": "City",
    "gstin": "GSTIN",
    "lead source": "Lead Source",
    "source": "Lead Source",
    "notes": "Notes",
    "remarks": "Notes",
}
for _col in CLIENT_IMPORT_COLUMNS:
    HEADER_ALIASES.setdefault(_col.lower(), _col)

# Alternate Phone is accepted but not required - a client may only have
# one number on file, which is fine, as long as the primary Phone is set.
REQUIRED_COLUMNS = ["Client Name", "Phone"]


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


EXAMPLE_ROWS = [
    {
        "Client Name": "Reference Client - Residential", "Contact Person": "", "Phone": "9812345670",
        "Alternate Phone": "", "Email": "reference.client@example.com", "Address": "123 Example Road, Indore",
        "Site Address": "Same as address", "City": "Indore", "GSTIN": "", "Lead Source": "Referral",
        "Notes": "Example row - delete before uploading your real data",
    },
    {
        "Client Name": "Reference Client - Commercial Pvt Ltd", "Contact Person": "Purchase Manager",
        "Phone": "9823456781", "Alternate Phone": "9834567892", "Email": "procurement@example.com",
        "Address": "456 Example Estate, Indore", "Site Address": "789 Example Site Road, Indore",
        "City": "Indore", "GSTIN": "23ABCDE1234F1Z5", "Lead Source": "Architect",
        "Notes": "Example row with GSTIN - delete before uploading your real data",
    },
]


def build_import_template() -> BytesIO:
    wb = Workbook()
    wb.remove(wb.active)
    write_sheet(
        wb, sheet_name="Client Import", title="Woodful Creations - Client Import Template",
        subtitle="Client Name and Phone are required for every row. Client ID is generated automatically - "
                  "do not add a Client ID column. Do not change the column headers.",
        columns=CLIENT_IMPORT_COLUMNS, rows=EXAMPLE_ROWS,
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


def validate_and_match_row(row: dict, existing_by_key: dict):
    """Validates one parsed row with the exact same rules the Client
    API enforces (validate_phone/validate_email/15-char GSTIN), and
    checks whether it looks like a duplicate of an existing client.
    Returns (result_dict, errors_list); never writes anything."""
    errors = []
    name = row.get("Client Name")
    if not name:
        errors.append("Client Name is required")

    phone = row.get("Phone")
    if not phone or not validate_phone(str(phone).strip()):
        errors.append("Please enter valid mobile number")

    email = row.get("Email")
    if email and not validate_email(email):
        errors.append(f"Invalid email: {email!r}")

    gstin = row.get("GSTIN")
    if gstin and len(gstin) != 15:
        errors.append(f"GSTIN must contain 15 characters (got {len(gstin)}): {gstin!r}")

    matched = existing_by_key.get(normalize_match_key(name, phone)) if name and phone else None

    result = {
        "name": name, "contact_person": row.get("Contact Person"), "phone": phone,
        "alternate_phone": row.get("Alternate Phone"), "email": email, "address": row.get("Address"),
        "site_address": row.get("Site Address"), "city": row.get("City"), "gstin": gstin,
        "lead_source": row.get("Lead Source"), "remarks": row.get("Notes"),
        "matched_client_id": matched.id if matched else None,
        "is_duplicate": matched is not None,
    }
    return result, errors
