"""E2E tests reuse the same MySQL + Redis fixtures as integration tests.

Pytest's conftest is tree-scoped from the test file *up*, not sideways. So
importing the integration conftest's fixtures here is the cleanest way to
share them without duplicating the setup code.
"""
from __future__ import annotations

# Re-export fixtures so they are discoverable from tests/e2e/.
from tests.integration.conftest import (  # noqa: F401
    mysql_container,
    redis_container,
    sia_env,
    requires_docker,
    db_session,
    api_client,
)
