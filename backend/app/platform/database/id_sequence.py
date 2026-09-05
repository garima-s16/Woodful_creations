from sqlalchemy import Column, Integer

from app.platform.database.database import Base


class IdSequence(Base):
    """Backs the centralized, incremental business_id generator (see
    app/platform/database/id_generator.generate_business_id). Deliberately minimal -
    this table has no meaning of its own; each row's autoincrement
    primary key is the only thing used, as the single monotonically
    increasing counter every entity's business_id is derived from.

    Using the database's native autoincrement (rather than a
    SELECT MAX()-then-write scheme) is what makes this safe under
    concurrent requests: two simultaneous inserts are guaranteed
    distinct, strictly increasing values by the database engine itself,
    with no read-then-write race window for two callers to land on the
    same number.
    """
    __tablename__ = "id_sequences"

    id = Column(Integer, primary_key=True, autoincrement=True)
