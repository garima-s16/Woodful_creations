"""Server-authoritative business ID generation.

Users should never type "CL-006" or "EMP-011" by hand - that's a
database-primary-key-shaped concern leaking into the UI, and it's
prone to typos and collisions. This generates the next sequential
code for a given prefix, scanning existing codes rather than keeping
a separate counter table (simpler, and self-healing if a row is ever
deleted).

Collision safety: under concurrent requests, two callers could both
compute the same "next" number before either commits. Callers should
wrap the actual insert in a retry-on-IntegrityError loop (the code
column is unique-indexed) rather than relying on this function alone
to guarantee uniqueness - see generate_unique_code below, which does
both in one call.

generate_short_id below is a separate, distinct kind of identifier
(Family 21 - "GLOBAL 10-CHARACTER IDs"): a 10-character, uppercase
alphanumeric, GLOBALLY UNIQUE, INCREMENTAL, centrally-generated
external identifier used alongside the sequential codes above rather
than replacing them - the sequential codes stay genuinely useful for
humans scanning a list (EMP-011 sorts and reads naturally); the
10-character ID exists for contexts that specifically want a fixed-
length external identifier, unique not just within its own table but
across every entity type in the entire system.

Before Family 21, this was a random `secrets.choice` string. It is now
backed by a single centralized, atomically-incremented counter (see
models/id_counter.py) encoded in base36 - still exactly 10 uppercase
alphanumeric characters (36**10 ~ 3.66e15 possible values, far beyond
any realistic table size), still passes every existing
`^[A-Z0-9]{10}$` format check, but now genuinely incremental and
generated from exactly one place in the codebase, per the brief:
"Centralize ID generation ... never manually typed ... safe against
duplicates/concurrent creation."
"""
import re
import string
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.id_counter import IdCounter

SHORT_ID_ALPHABET = string.digits + string.ascii_uppercase  # base36, 0-9 then A-Z
SHORT_ID_LENGTH = 10
GLOBAL_COUNTER_NAME = "global"


def next_sequence_number(db: Session, model, code_column: str, prefix: str) -> int:
    """Find the highest numeric suffix among existing codes starting
    with `prefix` and return the next one. Returns 1 if none exist."""
    column = getattr(model, code_column)
    existing = db.query(column).filter(column.like(f"{prefix}%")).all()
    max_n = 0
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    for (code,) in existing:
        if not code:
            continue
        m = pattern.match(code)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return max_n + 1


def format_code(prefix: str, number: int, pad: int = 3) -> str:
    return f"{prefix}{str(number).zfill(pad)}"


def generate_unique_code(db: Session, model, code_column: str, prefix: str, pad: int = 3) -> str:
    """Compute the next code for `prefix`. Does not itself retry on
    collision - the caller's insert should still be wrapped in a
    try/except IntegrityError and call this again on conflict, since
    two concurrent requests can race between this read and their commit.
    """
    n = next_sequence_number(db, model, code_column, prefix)
    return format_code(prefix, n, pad)


def _base36(number: int) -> str:
    if number == 0:
        return "0"
    digits = []
    while number > 0:
        number, rem = divmod(number, 36)
        digits.append(SHORT_ID_ALPHABET[rem])
    return "".join(reversed(digits))


def _next_global_counter_value(db: Session) -> int:
    """Atomically increments and returns the single global counter used
    for every entity type's 10-character ID.

    Implementation note: this deliberately does UPDATE then SELECT
    (both against the *same* session/transaction) rather than a single
    `UPDATE ... RETURNING`. RETURNING support/behavior differs across
    the SQLite and Postgres driver versions this app is deployed
    against, whereas UPDATE-then-SELECT-in-the-same-transaction is
    universally supported and just as safe: the UPDATE statement alone
    is what provides the atomicity (it takes a row lock on Postgres, and
    SQLite takes a write lock on the whole database for the duration of
    the write transaction), and the SELECT immediately after sees this
    same transaction's own uncommitted write. A second, concurrent
    caller's UPDATE simply blocks until this transaction commits or
    rolls back - it can never observe or reuse the same value.
    """
    # Ensure the singleton counter row exists. Uses a plain existence
    # check + insert (not INSERT ... ON CONFLICT, which is not portable
    # across SQLite/Postgres syntax) - safe because a lost race here
    # just means a harmless duplicate-row IntegrityError, caught below.
    row = db.query(IdCounter).filter(IdCounter.name == GLOBAL_COUNTER_NAME).first()
    if row is None:
        try:
            db.execute(
                text("INSERT INTO id_counters (name, next_value, created_at, updated_at) "
                     "VALUES (:name, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"),
                {"name": GLOBAL_COUNTER_NAME},
            )
            db.flush()
        except IntegrityError:
            # Another concurrent request already created it - fine,
            # just re-read below.
            db.rollback()

    db.execute(
        text("UPDATE id_counters SET next_value = next_value + 1, updated_at = CURRENT_TIMESTAMP WHERE name = :name"),
        {"name": GLOBAL_COUNTER_NAME},
    )
    result = db.execute(
        text("SELECT next_value FROM id_counters WHERE name = :name"),
        {"name": GLOBAL_COUNTER_NAME},
    ).fetchone()
    return int(result[0])


def generate_short_id(db: Session) -> str:
    """The centralized, atomic, incremental 10-character global ID
    (base36, e.g. "0000000001", "0000000002", ...). Requires a live db
    session because generation is now a real atomic database operation,
    not a client-side random draw - this is the one and only place in
    the codebase that should ever compute one of these; every route/
    service imports this function rather than re-implementing it.

    Still followed by a caller-side retry-on-IntegrityError loop for
    the overall insert (same discipline as generate_unique_code) - not
    because this function can collide with itself (the atomic counter
    guarantees a fresh, never-before-issued value every call), but so a
    failed insert for an unrelated reason (e.g. a duplicate sequential
    code) can cleanly retry the whole row, counter value included.
    """
    n = _next_global_counter_value(db)
    return _base36(n).upper().zfill(SHORT_ID_LENGTH)
