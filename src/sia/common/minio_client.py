"""MinIO / S3-compatible client for report archival (ARCHITECTURE_REVIEW §B-17).

The design called for MinIO to store PDF / HTML report artifacts, but the
original implementation stored everything in MySQL `Report.content_json`.
This module closes that gap.

Configured via `SIA_MINIO_*` env vars (see `sia.config.MinIOSettings`).
Gated by the `minio.enabled` Helm value and `MinIOSettings.enabled`.

All calls go through `resilient_call(minio_breaker, ...)` so transient
network glitches retry and persistent outages fast-fail without blocking
the report generation path (reports can fall back to DB-only storage).

Operations:
  * put_report(report_id, report_type, content_bytes, content_type)
      → object_key  (also stored in Report.pdf_object_key column)
  * get_report_url(object_key, expiry_seconds)
      → pre-signed HTTPS URL for the Web UI download button
  * ensure_bucket()
      → idempotent bucket + versioning setup at startup
"""

from __future__ import annotations

import logging
from datetime import timedelta
from io import BytesIO
from typing import TYPE_CHECKING, Any

from sia.common.resilience import minio_breaker, resilient_call
from sia.config import get_settings

if TYPE_CHECKING:
    from minio import Minio

logger = logging.getLogger(__name__)

_client: "Minio | None" = None


def _build_client() -> "Minio":
    """Construct the underlying Minio SDK client with configured credentials."""
    from minio import Minio  # late import so the dep is optional at dev time

    s = get_settings().minio
    return Minio(
        endpoint=s.endpoint,            # host:port
        access_key=s.access_key,
        secret_key=s.secret_key,
        secure=s.secure,
    )


def get_client() -> "Minio":
    """Return the process-wide MinIO client singleton."""
    global _client
    if _client is None:
        _client = _build_client()
    return _client


async def ensure_bucket() -> None:
    """Create the configured bucket if missing; enable versioning.

    Run once at consumer startup; safe to call repeatedly.
    """
    s = get_settings().minio
    if not s.enabled:
        logger.info("minio: disabled via config; skipping ensure_bucket")
        return

    client = get_client()

    async def _op() -> None:
        if not client.bucket_exists(s.bucket):
            client.make_bucket(s.bucket)
            logger.info("minio: created bucket %s", s.bucket)
        try:
            from minio.versioningconfig import VersioningConfig
            client.set_bucket_versioning(s.bucket, VersioningConfig("Enabled"))
        except Exception:  # noqa: BLE001
            logger.warning("minio: versioning not enabled on %s (may be s3-lite)", s.bucket,
                           exc_info=True)

    await resilient_call(minio_breaker, _op)


async def put_report(
    *,
    report_id: int,
    report_type: str,
    content_bytes: bytes,
    content_type: str = "application/pdf",
    extra_meta: dict | None = None,
) -> str:
    """Upload report bytes; return the object key stored on Report.pdf_object_key.

    Layout: `{report_type}/{YYYY}/{MM}/report-{id}.{ext}` so S3 listings stay
    tidy (one prefix per type × year × month).
    """
    from datetime import datetime

    s = get_settings().minio
    if not s.enabled:
        raise RuntimeError("minio is disabled; cannot put_report")

    now = datetime.now()
    ext = {"application/pdf": "pdf", "text/html": "html",
           "application/json": "json"}.get(content_type, "bin")
    key = f"{report_type}/{now:%Y/%m}/report-{report_id}.{ext}"

    client = get_client()
    meta = {"X-Amz-Meta-Report-Id": str(report_id),
            "X-Amz-Meta-Report-Type": report_type}
    if extra_meta:
        for k, v in extra_meta.items():
            meta[f"X-Amz-Meta-{k}"] = str(v)

    async def _op() -> None:
        client.put_object(
            bucket_name=s.bucket,
            object_name=key,
            data=BytesIO(content_bytes),
            length=len(content_bytes),
            content_type=content_type,
            metadata=meta,
        )

    await resilient_call(minio_breaker, _op)
    logger.info("minio: uploaded report id=%d → s3://%s/%s (%d bytes)",
                report_id, s.bucket, key, len(content_bytes))
    return key


async def get_report_url(object_key: str, expiry_seconds: int = 3600) -> str:
    """Generate a pre-signed GET URL. UI embeds this in the download button."""
    s = get_settings().minio
    client = get_client()

    async def _op() -> str:
        return client.presigned_get_object(
            bucket_name=s.bucket,
            object_name=object_key,
            expires=timedelta(seconds=expiry_seconds),
        )

    return await resilient_call(minio_breaker, _op)


async def safe_put_report(**kwargs) -> str | None:
    """Best-effort variant: upload if possible, return None on breaker open.

    Use this from hot paths (report generation) so an outage doesn't stop
    the DB record from being written. The operator can later batch-upload
    missing PDFs via a reconcile script.
    """
    from sia.common.resilience import CircuitOpenError

    try:
        return await put_report(**kwargs)
    except CircuitOpenError:
        logger.warning("minio breaker open; skipping upload for report_id=%s",
                       kwargs.get("report_id"))
        return None
    except Exception:  # noqa: BLE001
        logger.exception("minio upload failed for report_id=%s",
                         kwargs.get("report_id"))
        return None
