"""Add User.employee_id - a real foreign key link from a login account
to its Employee record, so "my tasks" and similar self-service features
can resolve the current user to their employee correctly instead of
matching full_name against Employee.name (which breaks silently on any
spelling difference and has no database-level integrity guarantee).

This column has an inline foreign key, which SQLite's ALTER TABLE
cannot add directly (see migration 0004's docstring for the full
explanation) - batch mode with a naming convention is required here,
covering any other unnamed constraints reflected from the existing
`users` table too, not just this new one.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def upgrade() -> None:
    with op.batch_alter_table("users", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.add_column(sa.Column(
            "employee_id", sa.Integer(),
            sa.ForeignKey("employees.id", name="fk_users_employee_id_employees"), nullable=True,
        ))
        batch_op.create_index("ix_users_employee_id", ["employee_id"])


def downgrade() -> None:
    with op.batch_alter_table("users", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.drop_index("ix_users_employee_id")
        batch_op.drop_column("employee_id")
