"""Unit tests for MinIO client (ARCHITECTURE_REVIEW §B-17)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_safe_put_report_returns_none_on_breaker_open(monkeypatch):
    """safe_put_report must never raise — returns None on CB open."""
    from sia.common import minio_client
    from sia.common.resilience import CircuitOpenError

    async def _raise(**kw):
        raise CircuitOpenError("breaker open")

    monkeypatch.setattr(minio_client, "put_report", _raise)
    result = await minio_client.safe_put_report(
        report_id=42, report_type="daily",
        content_bytes=b"x", content_type="application/pdf",
    )
    assert result is None


@pytest.mark.asyncio
async def test_safe_put_report_returns_none_on_generic_error(monkeypatch):
    from sia.common import minio_client

    async def _raise(**kw):
        raise RuntimeError("s3 offline")

    monkeypatch.setattr(minio_client, "put_report", _raise)
    result = await minio_client.safe_put_report(
        report_id=42, report_type="daily",
        content_bytes=b"x", content_type="application/pdf",
    )
    assert result is None


@pytest.mark.asyncio
async def test_safe_put_report_passes_result_on_success(monkeypatch):
    from sia.common import minio_client

    async def _ok(**kw):
        return "daily/2026/04/report-42.pdf"

    monkeypatch.setattr(minio_client, "put_report", _ok)
    result = await minio_client.safe_put_report(
        report_id=42, report_type="daily",
        content_bytes=b"x", content_type="application/pdf",
    )
    assert result == "daily/2026/04/report-42.pdf"


@pytest.mark.asyncio
async def test_put_report_generates_typed_object_key(monkeypatch):
    """Object key layout: <type>/<YYYY>/<MM>/report-<id>.<ext>."""
    from datetime import datetime
    from unittest.mock import Mock as _Mock

    from sia.common import minio_client

    fake_client = _Mock()
    fake_settings = _Mock()
    fake_settings.minio.enabled = True
    fake_settings.minio.bucket = "sia-reports"

    with patch.object(minio_client, "get_client", return_value=fake_client), \
         patch.object(minio_client, "get_settings", return_value=fake_settings), \
         patch("sia.common.minio_client.datetime") as dt_mock:
        dt_mock.now = lambda: datetime(2026, 4, 23)

        # Stub resilient_call to directly call the op
        async def _direct(breaker, fn, *a, **kw):
            return await fn(*a, **kw)

        with patch.object(minio_client, "resilient_call", _direct):
            key = await minio_client.put_report(
                report_id=42, report_type="daily",
                content_bytes=b"x" * 100, content_type="application/pdf",
            )

    assert key == "daily/2026/04/report-42.pdf"
    fake_client.put_object.assert_called_once()
    call_kwargs = fake_client.put_object.call_args.kwargs
    assert call_kwargs["bucket_name"] == "sia-reports"
    assert call_kwargs["object_name"] == "daily/2026/04/report-42.pdf"
    assert call_kwargs["content_type"] == "application/pdf"
    assert call_kwargs["length"] == 100


def test_disabled_config_prevents_upload():
    """If minio.enabled = False, put_report raises RuntimeError early."""
    import asyncio

    from sia.common import minio_client

    fake_settings = MagicMock()
    fake_settings.minio.enabled = False

    with patch.object(minio_client, "get_settings", return_value=fake_settings):
        with pytest.raises(RuntimeError, match="disabled"):
            asyncio.run(minio_client.put_report(
                report_id=1, report_type="daily",
                content_bytes=b"", content_type="application/pdf",
            ))
