#!/usr/bin/env python3
"""Initialize database tables and seed data."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from sia.common.database import init_db, close_db  # noqa: E402
from sia.common.redis import ensure_consumer_groups, close_redis  # noqa: E402


async def main() -> None:
    print("Initializing database tables...")
    await init_db()
    print("Database tables created.")

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
