"""Shared idempotency guards for Alembic migrations.

Root cause this exists to prevent: an existing database may have
tables/columns that a migration would still try to create from
scratch (e.g. if it was ever built via Base.metadata.create_all()
independently of Alembic's own tracking, or if a prior migration
attempt partially completed). Every migration's upgrade()/downgrade()
should use these instead of calling op.create_table/add_column/
create_index directly, so a create/add is always a genuine no-op (not
an error) when the target already exists.
"""
from alembic import op
import sqlalchemy as sa


def table_exists(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def column_exists(bind, table: str, name: str) -> bool:
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return False
    return any(c["name"] == name for c in insp.get_columns(table))


def index_exists(bind, table: str, name: str) -> bool:
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return False
    return any(ix["name"] == name for ix in insp.get_indexes(table))


def create_table_if_missing(bind, name: str, *columns_and_constraints, **kw) -> bool:
    """Returns True if the table was actually created (so a caller can
    decide whether to also seed default rows into it), False if it
    already existed and nothing was done."""
    if table_exists(bind, name):
        return False
    op.create_table(name, *columns_and_constraints, **kw)
    return True


def add_column_if_missing(bind, table: str, column: sa.Column) -> bool:
    if column_exists(bind, table, column.name):
        return False
    # batch_alter_table, not a plain op.add_column: SQLite cannot add a
    # column with an inline ForeignKey via a normal ALTER TABLE ("No
    # support for ALTER of constraints in SQLite dialect") - it
    # requires a copy-and-rebuild, which batch mode handles. On
    # databases that support a real ALTER (Postgres/Neon) this behaves
    # identically to the plain call, so every existing caller of this
    # helper is unaffected either way.
    with op.batch_alter_table(table) as batch_op:
        batch_op.add_column(column)
    return True


def create_index_if_missing(bind, index_name: str, table: str, columns, **kw) -> bool:
    if index_exists(bind, table, index_name):
        return False
    op.create_index(index_name, table, columns, **kw)
    return True


def column_is_integer_type(bind, table: str, column: str) -> bool:
    """True if the column's actual reflected type is an integer type
    (not yet converted to Numeric/Decimal). Used to guard a type
    ALTER (e.g. Integer -> Numeric) so it's only attempted when the
    column genuinely still needs it - unlike create_table/add_column,
    SQLite's batch-mode rebuild doesn't error on a redundant ALTER, but
    blindly re-asserting the WRONG existing_type (e.g. claiming
    Integer when the column is already Numeric, as it would be on a
    database built via create_all() against current models) risks
    Alembic generating a conversion inappropriate for data that's
    already the target type. Returns False (skip the alter) if the
    table or column doesn't exist at all, rather than raising."""
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return False
    for col in insp.get_columns(table):
        if col["name"] == column:
            return isinstance(col["type"], sa.Integer)
    return False
