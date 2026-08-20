from sqlalchemy import Column, Integer, BigInteger, String

from app.models.base import BaseModel


class IdCounter(BaseModel):
    """Backs the centralized, atomic, incremental global ID sequence
    (see utils/id_generator.py). One singleton row (`name="global"`) is
    used for every entity type in the system - "global" IDs, not one
    counter per entity - so a business_id is guaranteed unique across
    the entire database, not just within its own table, matching Family
    21's "GLOBAL 10-CHARACTER IDs" requirement literally.

    Deliberately a real table, not an in-process counter: an in-memory
    counter would (a) reset to a wrong value on every server restart
    unless it re-scanned every table on boot, and (b) not be shared
    across multiple backend worker processes. A single-row DB table
    with an atomic UPDATE is the standard, portable way to hand out a
    strictly increasing integer safely under concurrent writers on both
    SQLite (whole-DB write lock for the duration of the transaction)
    and Postgres (row-level lock acquired by the UPDATE itself) without
    requiring SELECT ... FOR UPDATE or a RETURNING clause that might not
    be available on every target engine/driver version.
    """
    __tablename__ = "id_counters"

    name = Column(String(50), unique=True, nullable=False, index=True)
    next_value = Column(BigInteger, nullable=False, default=0)
