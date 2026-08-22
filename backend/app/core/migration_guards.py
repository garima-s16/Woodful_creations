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
    op.add_column(table, column)
    return True


def create_index_if_missing(bind, index_name: str, table: str, columns, **kw) -> bool:
    if index_exists(bind, table, index_name):
        return False
    op.create_index(index_name, table, columns, **kw)
    return True
