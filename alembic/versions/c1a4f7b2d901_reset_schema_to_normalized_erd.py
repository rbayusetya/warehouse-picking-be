"""reset schema to the normalized warehouse ERD

This migration is intentionally destructive. The project is still in
development and the existing database may be recreated, so the old
denormalized tables are replaced with the schema represented by the
SQLAlchemy models.
"""

from typing import Sequence, Union

from alembic import op

from app.database import Base
from app import models  # noqa: F401


revision: str = "c1a4f7b2d901"
down_revision: Union[str, None] = "befa64175889"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
