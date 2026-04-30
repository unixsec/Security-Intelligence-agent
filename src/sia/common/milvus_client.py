"""Milvus client + embedding service for v0.4 dedup levels 2 and 3.

Why
---
Level 1 dedup (SHA-256 fingerprint) catches re-publication of identical
``(title, url)`` pairs but misses paraphrased coverage of the same incident
across different feeds. Levels 2 and 3 use embedding similarity:

* **Level 2 — same-day**: cosine ≥ 0.85 within the last 24 h → flag as
  duplicate-of-existing.
* **Level 3 — cross-day**: cosine ≥ 0.80 within the last 14 days → flag as
  resurfacing of a known story.

Decisions
---------
* Embedding model is **local** (sentence-transformers MiniLM-L6-v2, 384 dim,
  ~80 MB on disk). We deliberately do **not** call a cloud embedding API:
  raw intel content goes through the LLM gateway which already enforces
  on-egress anonymization, but embedding APIs would bypass that boundary.
* Milvus collection is created lazily on first write so unit tests that run
  without a live Milvus don't have to mock the bootstrap.
* Failure mode: any embed/insert/search exception is caught at the analyzer
  layer; dedup levels 2/3 degrade to "no decision" (NOT "is duplicate"), so
  Milvus outage cannot suppress real intel.

Performance notes
-----------------
* Embedding latency on CPU: ~30 ms for a typical title+content pair.
* Search latency: < 50 ms per query for collections up to ~1M items.
* Memory: ~150 MB for 100k items with HNSW M=16.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Module-level singletons — embedding model is heavy (~80 MB load), Milvus
# client maintains a connection pool. Lazy init on first use.
_milvus = None
_embedder = None


def is_enabled() -> bool:
    """Return True iff Milvus dedup is enabled in settings."""
    try:
        from sia.config import get_settings
        return bool(get_settings().milvus.enabled)
    except Exception:
        return False


# ─── Embedding ────────────────────────────────────────────────────────────


def get_embedder():
    """Lazy-load the sentence-transformers model."""
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            from sia.config import get_settings
            model_name = get_settings().milvus.embedding_model
            _embedder = SentenceTransformer(model_name)
            logger.info("Loaded embedding model: %s", model_name)
        except Exception:
            logger.exception("Failed to load embedding model; dedup levels 2/3 will be skipped")
            _embedder = False  # sentinel: tried + failed
    return _embedder if _embedder is not False else None


def embed_text(text: str) -> list[float] | None:
    """Embed a single text. Returns None on any failure."""
    if not text or not text.strip():
        return None
    embedder = get_embedder()
    if embedder is None:
        return None
    try:
        # encode returns a numpy array; convert to plain Python list for JSON-friendly storage.
        vec = embedder.encode(text[:8000], normalize_embeddings=True)
        return vec.tolist()
    except Exception:
        logger.exception("embedding failed")
        return None


# ─── Milvus client ────────────────────────────────────────────────────────


def _get_client():
    """Lazy-connect to Milvus. Returns None if unavailable."""
    global _milvus
    if _milvus is False:
        return None
    if _milvus is not None:
        return _milvus
    try:
        from pymilvus import MilvusClient

        from sia.config import get_settings
        cfg = get_settings().milvus
        uri = f"http://{cfg.host}:{cfg.port}"
        kwargs = {"uri": uri}
        if cfg.token:
            kwargs["token"] = cfg.token
        _milvus = MilvusClient(**kwargs)
        _ensure_collection(_milvus, cfg.collection_name, cfg.embedding_dim)
        logger.info("Connected to Milvus at %s", uri)
        return _milvus
    except Exception:
        logger.exception("Milvus connect failed; dedup levels 2/3 will be skipped")
        _milvus = False  # sentinel
        return None


def _ensure_collection(client, name: str, dim: int) -> None:
    """Create the intel_vectors collection if missing.

    Schema:
        id          INT64    primary, auto_id=False (we use intel.id)
        embedding   FLOAT_VECTOR[dim]
        intel_id    INT64
        category    VARCHAR(64)
        collected_at INT64   epoch seconds for time-window filtering
        title       VARCHAR(512)
    """
    if client.has_collection(collection_name=name):
        return

    from pymilvus import DataType
    schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
    schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
    schema.add_field(field_name="embedding", datatype=DataType.FLOAT_VECTOR, dim=dim)
    schema.add_field(field_name="intel_id", datatype=DataType.INT64)
    schema.add_field(field_name="category", datatype=DataType.VARCHAR, max_length=64)
    schema.add_field(field_name="collected_at", datatype=DataType.INT64)
    schema.add_field(field_name="title", datatype=DataType.VARCHAR, max_length=512)

    index_params = client.prepare_index_params()
    # HNSW gives the best latency/recall for ~1M vector collections; cosine
    # because our embedder normalises L2 already so dot ≈ cosine.
    index_params.add_index(
        field_name="embedding",
        index_type="HNSW",
        metric_type="COSINE",
        params={"M": 16, "efConstruction": 200},
    )
    client.create_collection(collection_name=name, schema=schema, index_params=index_params)
    logger.info("Created Milvus collection %s (dim=%d, HNSW/COSINE)", name, dim)


# ─── Public ops ───────────────────────────────────────────────────────────


def upsert_vector(
    *,
    intel_id: int,
    embedding: list[float],
    category: str,
    title: str,
    collected_at_epoch: int,
) -> bool:
    """Insert / overwrite a vector. Returns True on success."""
    client = _get_client()
    if client is None:
        return False
    try:
        from sia.config import get_settings
        client.upsert(
            collection_name=get_settings().milvus.collection_name,
            data=[{
                "id": int(intel_id),
                "embedding": embedding,
                "intel_id": int(intel_id),
                "category": (category or "")[:64],
                "collected_at": int(collected_at_epoch),
                "title": (title or "")[:512],
            }],
        )
        return True
    except Exception:
        logger.exception("milvus upsert failed for intel_id=%s", intel_id)
        return False


def search_similar(
    embedding: list[float],
    *,
    top_k: int = 5,
    min_collected_at_epoch: int | None = None,
    exclude_intel_id: int | None = None,
) -> list[dict[str, Any]]:
    """Search for similar vectors; result list ordered by descending cosine.

    Each hit: ``{"intel_id", "title", "category", "similarity", "collected_at"}``.
    Returns ``[]`` when Milvus is disabled or an error occurs.
    """
    client = _get_client()
    if client is None:
        return []
    try:
        from sia.config import get_settings
        cfg = get_settings().milvus

        filter_parts: list[str] = []
        if min_collected_at_epoch is not None:
            filter_parts.append(f"collected_at >= {int(min_collected_at_epoch)}")
        if exclude_intel_id is not None:
            filter_parts.append(f"intel_id != {int(exclude_intel_id)}")
        flt = " and ".join(filter_parts) if filter_parts else None

        res = client.search(
            collection_name=cfg.collection_name,
            data=[embedding],
            limit=top_k,
            output_fields=["intel_id", "title", "category", "collected_at"],
            search_params={"metric_type": "COSINE", "params": {"ef": 64}},
            filter=flt,
        )
        hits = res[0] if res else []
        out = []
        for hit in hits:
            sim = float(hit.get("distance", 0))   # for COSINE Milvus returns similarity in [-1,1]
            entity = hit.get("entity", {}) or {}
            out.append({
                "intel_id": int(entity.get("intel_id") or 0),
                "title": entity.get("title") or "",
                "category": entity.get("category") or "",
                "collected_at": int(entity.get("collected_at") or 0),
                "similarity": sim,
            })
        return out
    except Exception:
        logger.exception("milvus search failed")
        return []
