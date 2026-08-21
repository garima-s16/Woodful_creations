"""Client recognition for order intake.

Business rule: when a new order is entered with a client name + phone
(rather than an already-selected client_id), decide whether this is the
same client returning or a genuinely different person, using BOTH name
and phone - neither alone is sufficient:

    NAME matches AND PHONE matches  -> reuse the existing Client, create a new Order
    otherwise (any other combination) -> create a new Client, create a new Order

This deliberately does not use fuzzy/similarity matching (unlike
GET /api/clients/check-duplicates, which is an advisory nudge for a
human to review) - this decision is made unattended as part of order
creation, so it needs a bright-line rule a person could audit, not a
similarity score. A near-miss on either name or phone must create a
new client rather than silently guess.
"""
import re
from typing import Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.client import Client
from app.utils.id_generator import generate_unique_code, generate_business_id


def normalize_name(name: Optional[str]) -> str:
    """Case-insensitive, whitespace-collapsed - "Garima", " garima ",
    and "GARIMA" all normalize to the same key. Internal punctuation is
    left alone (a name is not a phone number), since stripping it could
    quietly merge genuinely different names."""
    if not name:
        return ""
    return re.sub(r"\s+", " ", name.strip()).lower()


def normalize_phone(phone: Optional[str]) -> str:
    """Strips everything but digits, so "97578 84676", "97578-84676",
    and "(97578) 84676" all normalize to the same key. Does not strip
    or add a country code - "9757884676" and "919757884676" are treated
    as different numbers rather than guessing they're the same person
    with/without a +91 prefix."""
    if not phone:
        return ""
    return re.sub(r"\D", "", phone)


def find_matching_client(db: Session, name: Optional[str], phone: Optional[str]) -> Optional[Client]:
    """Returns the existing Client only if BOTH normalized name and
    normalized phone match some existing client - None otherwise
    (including when name or phone is empty/invalid, since a match
    can't be determined at all in that case, and Client Master
    validation will reject an empty/invalid phone on creation anyway)."""
    name_key = normalize_name(name)
    phone_key = normalize_phone(phone)
    if not name_key or not phone_key:
        return None

    # Compare in Python rather than push normalization into SQL - the
    # client table isn't large enough for this to be a performance
    # concern, and it keeps exactly one normalization implementation
    # (this module) as the source of truth for what "matches" means.
    for candidate in db.query(Client).all():
        if normalize_name(candidate.name) == name_key and normalize_phone(candidate.phone) == phone_key:
            return candidate
    return None


def find_or_create_client(db: Session, name: str, phone: str, **extra_fields) -> Tuple[Client, bool]:
    """Returns (client, created). Reuses an existing client only on a
    full name+phone match; otherwise creates a new one through the same
    generate_unique_code/generate_business_id path every other client
    creation uses, so a client created this way is indistinguishable
    from one created through the regular Client form.

    extra_fields are only applied when actually creating a new client -
    reusing an existing client never overwrites its stored details
    (e.g. its address) just because a new order mentioned different
    incidental details; only its own edit flow should ever change that.
    """
    existing = find_matching_client(db, name, phone)
    if existing:
        return existing, False

    # This path constructs Client(...) directly via the ORM rather than
    # through the ClientCreate Pydantic schema, so the schema's own
    # phone validator never runs here - it has to be checked explicitly
    # before a genuinely new client can be created this way. Reusing an
    # existing client (the branch above) never needs this: an existing
    # client's phone was already validated when IT was created.
    from app.utils.validators import validate_phone
    if not validate_phone((phone or "").strip()):
        raise ValueError("Please enter valid mobile number")

    for _ in range(5):
        code = generate_unique_code(db, Client, "client_code", "CL-")
        client = Client(
            client_code=code, business_id=generate_business_id(db),
            name=(name or "").strip(), phone=(phone or "").strip(), **extra_fields,
        )
        db.add(client)
        try:
            db.flush()
            return client, True
        except IntegrityError:
            db.rollback()
            continue
    raise RuntimeError("Unable to generate a unique client code, please try again")
