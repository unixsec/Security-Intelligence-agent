#!/usr/bin/env python3
"""Initialize database tables (alembic-driven) and Redis consumer groups.

DEP-4: schema is now versioned through alembic. ``alembic upgrade head``
runs every migration in ``migrations/versions/`` against the live DB, so
operations get a deterministic, replay-able history instead of the v0.2
``Base.metadata.create_all`` snapshot.

Backwards compatibility: when ``migrations/versions/`` is empty (fresh
checkout that hasn't generated a baseline yet) we fall back to the legacy
``init_db()`` so test environments still bootstrap.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sia.common.database import init_db, close_db  # noqa: E402
from sia.common.redis import ensure_consumer_groups, close_redis  # noqa: E402


def _versions_dir_has_migrations() -> bool:
    versions_dir = PROJECT_ROOT / "migrations" / "versions"
    if not versions_dir.is_dir():
        return False
    return any(p.suffix == ".py" and p.name != "__init__.py" for p in versions_dir.iterdir())


def _run_alembic_upgrade() -> None:
    """Run ``alembic upgrade head`` in-process so we share the same env."""
    from alembic import command
    from alembic.config import Config

    cfg_path = PROJECT_ROOT / "alembic.ini"
    cfg = Config(str(cfg_path))
    # alembic.ini ships with a placeholder URL; env.py overrides via SIA settings.
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    command.upgrade(cfg, "head")


async def main() -> None:
    if _versions_dir_has_migrations():
        print("Running alembic upgrade head ...")
        # alembic.command runs synchronously; do it in a thread so we don't
        # block the event loop (the only async work happens after).
        await asyncio.to_thread(_run_alembic_upgrade)
        print("alembic upgrade complete.")
    else:
        print("No alembic versions present; falling back to metadata.create_all (dev only).")
        await init_db()
        print("Database tables created (dev mode).")

    print("Initializing Redis consumer groups...")
    try:
        await ensure_consumer_groups()
        print("Redis consumer groups created.")
    except Exception as e:
        print(f"Redis initialization skipped: {e}")

    await close_db()
    await close_redis()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
