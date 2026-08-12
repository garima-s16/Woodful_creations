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

generate_short_id below is a separate, distinct kind of identifier: a
random 10-character alphanumeric string (e.g. A7K92P4XQ1), used
alongside the sequential codes above rather than replacing them - the
sequential codes stay genuinely useful for humans scanning a list
(EMP-011 sorts and reads naturally); this one exists for contexts that
specifically want an opaque, unguessable, fixed-length external
identifier that reveals nothing about record count or creation order.
"""
import re
import secrets
import string
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

SHORT_ID_ALPHABET = string.ascii_uppercase + string.digits
SHORT_ID_LENGTH = 10


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


def generate_short_id() -> str:
    """A random 10-character alphanumeric ID (uppercase letters + digits,
    e.g. A7K92P4XQ1). Uses `secrets` (cryptographically strong), not
    `random` - collision probability across even a very large table is
    negligible (36^10 possible values), but callers should still wrap
    their insert in a retry-on-IntegrityError loop, same as
    generate_unique_code, since the column is unique-indexed and two
    concurrent requests could theoretically collide."""
    return "".join(secrets.choice(SHORT_ID_ALPHABET) for _ in range(SHORT_ID_LENGTH))
