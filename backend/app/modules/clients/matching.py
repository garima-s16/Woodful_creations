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
import difflib
import hashlib
import re
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text as sa_text

from app.modules.clients.models import Client
from app.platform.database.id_generator import generate_unique_code, generate_business_id

# Typo/possible-duplicate detection must be the SAME
# logic everywhere it's used (UI master-data search AND Excel import), never
# reimplemented per call site. 0.8 is the same threshold GET
# /api/clients/check-duplicates has used since it was introduced - kept here
# so the Excel importer can share it exactly rather than drifting.
FUZZY_MATCH_THRESHOLD = 0.8


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
    validation will reject an empty/invalid phone on creation anyway).

    Filters by the indexed phone column at the database level first,
    since every path that creates a Client (the regular API, the Excel
    importer, and this module's own find_or_create_client) validates
    phone down to exactly 10 digits before ever storing it - a direct
    equality filter on the normalized phone is therefore a safe,
    narrow candidate set, not an approximation. The final name
    comparison runs in Python only against that small set, not the
    entire table."""
    name_key = normalize_name(name)
    phone_key = normalize_phone(phone)
    if not name_key or not phone_key:
        return None

    candidates = db.query(Client).filter(Client.phone == phone_key).all()
    for candidate in candidates:
        if normalize_name(candidate.name) == name_key and normalize_phone(candidate.phone) == phone_key:
            return candidate
    return None


def find_fuzzy_name_matches(db: Session, name: str, limit: int = 5,
                             candidates: Optional[List[Client]] = None) -> List[Client]:
    """Non-blocking "possible duplicate" nudge -
    catches typo-variants ("Fevikol" vs "Fevicol") and substrings via
    fuzzy similarity. Distinct from find_matching_client above: that
    function is a bright-line exact-match rule used to make an unattended
    decision (order intake); this one is an advisory signal for a human
    to review (both GET /api/clients/check-duplicates and the Client
    Excel importer call this same function, so the two can never
    disagree about what counts as a "possible" match) and never by
    itself creates, reuses, or rejects a record.
    """
    name_lower = (name or "").strip().lower()
    if not name_lower:
        return []
    matches = []
    for candidate in (candidates if candidates is not None else db.query(Client).all()):
        c_name_lower = candidate.name.lower()
        if name_lower in c_name_lower or c_name_lower in name_lower:
            matches.append(candidate)
            continue
        similarity = difflib.SequenceMatcher(None, name_lower, c_name_lower).ratio()
        if similarity >= FUZZY_MATCH_THRESHOLD:
            matches.append(candidate)
    return matches[:limit]


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

    Guarded by a PostgreSQL advisory lock scoped to this specific
    (name, phone) pair for the duration of the find-then-create check -
    otherwise two simultaneous requests for the same new client could
    both find no existing match and both create a duplicate Client row.
    No DB-level uniqueness constraint protects against this the way it
    does for other duplicate-creation races this app guards against:
    unlike a client-wide product rate row, an existing Client can have
    real Estimates/Orders/Payments depending on it, so a future
    duplicate could never be safely auto-merged or deleted the way
    those simpler rows could - preventing the race here is the only
    safe option. A no-op on SQLite (tests never run genuinely
    concurrent requests against it)."""
    lock_key = None
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        normalized = f"{normalize_name(name)}|{normalize_phone(phone)}"
        lock_key = int(hashlib.md5(normalized.encode()).hexdigest()[:15], 16)
        db.execute(sa_text("SELECT pg_advisory_lock(:key)"), {"key": lock_key})
    try:
        existing = find_matching_client(db, name, phone)
        if existing:
            return existing, False

        # This path constructs Client(...) directly via the ORM rather than
        # through the ClientCreate Pydantic schema, so the schema's own
        # phone validator never runs here - it has to be checked explicitly
        # before a genuinely new client can be created this way. Reusing an
        # existing client (the branch above) never needs this: an existing
        # client's phone was already validated when IT was created.
        from app.shared.validators import validate_phone
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
    finally:
        if lock_key is not None:
            db.execute(sa_text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key})
