"""Health-check and unauthenticated-endpoint integration tests."""

from __future__ import annotations

import pytest

from tests.integration.conftest import requires_docker


pytestmark = [pytest.mark.integration, requires_docker]


@pytest.mark.asyncio
async def test_health_endpoint_200(api_client):
    resp = await api_client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("status") in ("ok", "healthy")


@pytest.mark.asyncio
async def test_root_shows_version(api_client):
    resp = await api_client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Security Intelligence Agent"
    assert "version" in body


@pytest.mark.asyncio
async def test_protected_endpoint_requires_auth(api_client):
    """Calling /intelligence without creds returns 401."""
    resp = await api_client.get("/api/v1/intelligence")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_api_key_grants_access(api_client):
    """Using the test API key succeeds (admin role)."""
    resp = await api_client.get(
        "/api/v1/intelligence",
        headers={"X-API-Key": "ci-test-api-key"},
    )
    assert resp.status_code == 200
