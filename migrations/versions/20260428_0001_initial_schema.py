"""initial schema (v0.3 baseline)

Revision ID: 20260428_0001
Revises:
Create Date: 2026-04-28

Generates the schema from the live SQLAlchemy metadata. This is the
"baseline" migration: subsequent revisions should be created via
``alembic revision --autogenerate -m '<message>'`` and edited as needed
before merging.

DEP-4: prior to this, ``init_db()`` called ``Base.metadata.create_all`` so
production databases had no version markers and could not be evolved
safely. After this migration runs once, ``alembic_version`` is populated
and standard alembic upgrade/downgrade workflow applies.
"""

from __future__ import annotations

from alembic import op
from sqlalchemy.engine import reflection

import sia.models  # noqa: F401  -- triggers Base.metadata population
from sia.common.database import Base


# revision identifiers, used by Alembic.
revision = "20260428_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create every table declared on Base.metadata.

    We use create_all() rather than emitting hand-written ``op.create_table``
    blocks for every model because (a) the model count is high (>20), (b) the
    schema is the source of truth, and (c) future migrations are autogenerate
    diffs against this baseline.

    Idempotency: when the table already exists (ops re-run this on a database
    that was originally seeded with ``Base.metadata.create_all``), we skip
    creation and only stamp the alembic_version row.
    """
    bind = op.get_bind()
    inspector = reflection.Inspector.from_engine(bind)
    existing = set(inspector.get_table_names())

    tables_to_create = [t for t in Base.metadata.sorted_tables if t.name not in existing]
    for table in tables_to_create:
        table.create(bind, checkfirst=True)


def downgrade() -> None:
    """Drop every table this baseline created.

    This is intentionally destructive — downgrading from the baseline means
    "wipe the application schema". Production downgrade should always go
    through a more granular subsequent revision instead.
    """
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
