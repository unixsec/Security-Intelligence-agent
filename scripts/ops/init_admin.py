#!/usr/bin/env python3
"""Create the initial admin user.

Usage:
    PYTHONPATH=src python scripts/ops/init_admin.py
    PYTHONPATH=src python scripts/ops/init_admin.py --username admin --password 'SecureP@ss1'

Environment variables (alternative to CLI args):
    SIA_ADMIN_USERNAME  default: admin
    SIA_ADMIN_PASSWORD  default: auto-generated
    SIA_ADMIN_EMAIL     default: admin@localhost
"""

from __future__ import annotations

import argparse
import asyncio
import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from sia.auth.password import hash_password  # noqa: E402
from sia.common.database import get_db_context, init_db, close_db  # noqa: E402
from sia.models.user import User  # noqa: E402


def generate_password(length: int = 16) -> str:
    """Generate a random password that meets default policy."""
    import string
    chars = string.ascii_letters + string.digits + "!@#$%"
    while True:
        pw = "".join(secrets.choice(chars) for _ in range(length))
        if (any(c.isupper() for c in pw) and any(c.islower() for c in pw)
                and any(c.isdigit() for c in pw)):
            return pw


async def main() -> None:
    parser = argparse.ArgumentParser(description="Create initial admin user")
    parser.add_argument("--username", default=os.environ.get("SIA_ADMIN_USERNAME", "admin"))
    parser.add_argument("--password", default=os.environ.get("SIA_ADMIN_PASSWORD", ""))
    parser.add_argument("--email", default=os.environ.get("SIA_ADMIN_EMAIL", "admin@localhost"))
    args = parser.parse_args()

    password = args.password or generate_password()

    await init_db()

    from sqlalchemy import select

    async with get_db_context() as session:
        # Check if admin already exists
        result = await session.execute(
            select(User).where(User.username == args.username)
        )
        existing = result.scalar_one_or_none()
        if existing:
            print(f"User '{args.username}' already exists (id={existing.id}, role={existing.role}). Skipping.")
            await close_db()
            return

        user = User(
            username=args.username,
            email=args.email,
            display_name="System Administrator",
            hashed_password=hash_password(password),
            role="admin",
            auth_provider="local",
            status="active",
        )
        session.add(user)

    await close_db()

    print(f"Admin user created successfully.")
    print(f"  Username: {args.username}")
    print(f"  Email:    {args.email}")
    print(f"  Role:     admin")
    if not args.password:
        print(f"  Password: {password}")
        print(f"  (auto-generated — change it after first login)")


if __name__ == "__main__":
    asyncio.run(main())
