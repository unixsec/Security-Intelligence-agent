"""Tests for API endpoints using FastAPI TestClient."""

import pytest
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client():
    """Create an async test client with mocked DB/Redis."""
    with patch("sia.common.database.init_db", new_callable=AsyncMock), \
         patch("sia.common.redis.ensure_consumer_groups", new_callable=AsyncMock), \
         patch("sia.common.redis.close_redis", new_callable=AsyncMock), \
         patch("sia.common.database.close_db", new_callable=AsyncMock):
        from sia.main import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


class TestRootEndpoint:
    @pytest.mark.asyncio
    async def test_root(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Security Intelligence Agent"
        assert "version" in data


class TestOpenAPISchema:
    @pytest.mark.asyncio
    async def test_openapi_available(self, client):
        resp = await client.get("/api/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert "paths" in schema
        assert "/api/v1/intelligence" in schema["paths"]
        assert "/api/v1/sources" in schema["paths"]
        assert "/api/v1/reports" in schema["paths"]
