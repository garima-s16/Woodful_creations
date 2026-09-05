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

generate_business_id below is the current, forward-looking generator for
that same kind of field: a centralized, incremental, 10-character
alphanumeric external ID (e.g. 000000014K), shared by every business
entity in the system (clients, suppliers, employees, products,
materials, estimates, orders, payments, tasks, production jobs,
expenses, projects, purchases, ...) rather than one scheme per entity
type. "Incremental" here means every ID is derived from a single
strictly-increasing database sequence (see IdSequence /
app/models/id_sequence.py) - two different entity types created back to
back get two different, ordered business_ids from the same counter, the
same way Stripe- or GitHub-style object IDs work. This is deliberately
not the human-readable "EST-001"-style prefix code - that field
continues to exist separately (estimate_code, client_code, ...) for
people scanning a list; business_id is the opaque system identifier that
should be used wherever a business object needs to be referenced,
exported, or looked up externally, and it is never typed in by hand.

generate_short_id below is the original, now-legacy generator this one
replaces for new code: a random (not incremental) 10-character
alphanumeric string. It remains here only because existing Alembic
migrations (0007, 0010) call it during one-time historical data
backfills, and a migration's behavior must never change after it has
already run against real databases. No new code should call it -
use generate_business_id instead.
"""
import re
import secrets
import string
from sqlalchemy.orm import Session

SHORT_ID_ALPHABET = string.ascii_uppercase + string.digits
SHORT_ID_LENGTH = 10

# Base36: digits then uppercase letters, so every generated business_id
# stays within the same [A-Z0-9]{10} shape already established (and
# already asserted by tests/platform/test_business_id.py) for the legacy random
# IDs - callers and UI don't need to know which generator produced a
# given value.
_BASE36_ALPHABET = string.digits + string.ascii_uppercase


def _to_base36(n: int) -> str:
    if n == 0:
        return _BASE36_ALPHABET[0]
    digits = []
    while n:
        n, remainder = divmod(n, 36)
        digits.append(_BASE36_ALPHABET[remainder])
    return "".join(reversed(digits))


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


def generate_business_id(db: Session) -> str:
    """The centralized, incremental, system-generated 10-character
    external ID for any business entity - see the module docstring.

    Implementation: insert one row into id_sequences and flush (not
    commit) to obtain its autoincrement primary key without ending the
    caller's transaction. That integer is guaranteed unique and
    strictly increasing by the database engine itself - concurrent
    callers each get a distinct number with no race window - then it's
    offset and base36-encoded to exactly 10 characters.

    The offset (10 * 36^9, i.e. base36 "A000000000") exists so every
    generated ID - including the very first one - includes a leading
    letter rather than being purely numeric. Without it, early
    sequence values base36-encode to something indistinguishable from
    a plain zero-padded decimal number (id=5 -> "0000000005", id=9 ->
    "0000000009"), defeating the entire point of an alphanumeric ID.
    The offset preserves strict ordering (it's a constant added before
    encoding, so relative order between any two IDs is unchanged) and
    leaves ~2.6 quadrillion IDs of headroom before it would ever need
    an 11th character.
    """
    from app.platform.database.id_sequence import IdSequence

    seq = IdSequence()
    db.add(seq)
    db.flush()
    offset = 10 * 36 ** 9  # base36 "A000000000"
    return _to_base36(offset + seq.id).rjust(SHORT_ID_LENGTH, _BASE36_ALPHABET[0])


def generate_short_id() -> str:
    """A random 10-character alphanumeric ID (uppercase letters + digits,
    e.g. A7K92P4XQ1). Uses `secrets` (cryptographically strong), not
    `random` - collision probability across even a very large table is
    negligible (36^10 possible values), but callers should still wrap
    their insert in a retry-on-IntegrityError loop, same as
    generate_unique_code, since the column is unique-indexed and two
    concurrent requests could theoretically collide."""
    return "".join(secrets.choice(SHORT_ID_ALPHABET) for _ in range(SHORT_ID_LENGTH))
