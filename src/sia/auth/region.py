"""Region awareness helpers (v0.4-8).

Used to enforce that identity writes (users, groups, api_keys) only
happen in the region designated as the **identity primary**. All regions
can serve identity *reads*; only the primary accepts mutations.

Configuration::

    SIA_REGION                 = "eu-west"
    SIA_REGION_IDENTITY_PRIMARY = "eu-west"   # the one allowed to write users

When the local region != identity primary, the API endpoints decorated
with :func:`require_identity_primary` return 503 with a hint to retry
against the primary's URL.
"""

from __future__ import annotations

import os

from fastapi import Depends, HTTPException


def current_region() -> str:
    return os.environ.get("SIA_REGION", "default")


def identity_primary() -> str:
    return os.environ.get("SIA_REGION_IDENTITY_PRIMARY", current_region())


def is_identity_primary() -> bool:
    return current_region() == identity_primary()


def require_identity_primary():
    """FastAPI dependency that 503s on non-primary regions."""

    async def _check() -> None:
        if not is_identity_primary():
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Identity writes are restricted to region "
                    f"'{identity_primary()}'; this is region "
                    f"'{current_region()}'. Retry against the primary."
                ),
            )

    return Depends(_check)
