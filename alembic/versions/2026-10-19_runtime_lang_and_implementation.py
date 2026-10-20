"""runtime lang and implementation

Revision ID: b5661534c08f
Revises:
Create Date: 2026-10-19 13:29:04.331378

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b5661534c08f'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the new columns as nullable first so this works on SQLite tables
    # that already contain rows.
    with op.batch_alter_table("python_app_runtimes") as batch_op:
        batch_op.add_column(
            sa.Column("lang", sqlmodel.sql.sqltypes.AutoString(length=25), nullable=True)
        )
        batch_op.add_column(
            sa.Column("implementation", sqlmodel.sql.sqltypes.AutoString(length=25), nullable=True)
        )

    # Backfill existing rows with sensible defaults.
    op.execute("UPDATE python_app_runtimes SET lang = 'Python' WHERE lang IS NULL")
    op.execute("UPDATE python_app_runtimes SET implementation = 'cpython' WHERE implementation IS NULL")

    # Then enforce the NOT NULL constraints to match the model.
    with op.batch_alter_table("python_app_runtimes") as batch_op:
        batch_op.alter_column("lang", nullable=False)
        batch_op.alter_column("implementation", nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("python_app_runtimes") as batch_op:
        batch_op.drop_column("implementation")
        batch_op.drop_column("lang")
