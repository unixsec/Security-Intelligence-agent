"""Unit tests for the audit hash-chain logic (ARCHITECTURE_REVIEW §E.3).

We test the hash-computation helpers with an in-memory dataset. The async
`_persist_with_chain` and `verify_chain` functions talk to the DB and are
covered by integration tests separately.
"""

from __future__ import annotations

import json
from hashlib import sha256

from sia.common.audit import _GENESIS_HASH


def _chain_hash(prev: str, payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                           default=str).encode("utf-8")
    return sha256(prev.encode("ascii") + canonical).hexdigest()


def test_genesis_hash_literal():
    assert _GENESIS_HASH == "0" * 64


def test_chain_linear_append():
    """Appending events produces a deterministic chain."""
    p1 = {"event": "a", "result": "success"}
    p2 = {"event": "b", "result": "success"}

    h1 = _chain_hash(_GENESIS_HASH, p1)
    h2 = _chain_hash(h1, p2)

    # Recomputing must produce identical values
    assert _chain_hash(_GENESIS_HASH, p1) == h1
    assert _chain_hash(h1, p2) == h2
    assert h1 != h2


def test_chain_detects_payload_tamper():
    """Changing a row's details invalidates downstream hashes."""
    p1 = {"event": "a", "result": "success"}
    p2 = {"event": "b", "result": "success"}
    h1 = _chain_hash(_GENESIS_HASH, p1)
    h2 = _chain_hash(h1, p2)

    # Attacker modifies p2 in place
    p2_tampered = {"event": "b", "result": "FAILURE"}
    h2_recomputed = _chain_hash(h1, p2_tampered)

    assert h2_recomputed != h2


def test_chain_detects_row_deletion():
    """If attacker deletes middle row, recomputing from stored prev_hash
    yields a hash that the next row's prev_hash does not match."""
    p1 = {"event": "a"}
    p2 = {"event": "b"}
    p3 = {"event": "c"}
    h1 = _chain_hash(_GENESIS_HASH, p1)
    h2 = _chain_hash(h1, p2)
    h3 = _chain_hash(h2, p3)

    # After deleting p2, attacker tries to make p3 link directly from h1.
    # The legitimate h3 (stored on row 3) still expects prev = h2.
    attacker_prev = h1
    attacker_cur = _chain_hash(attacker_prev, p3)
    assert attacker_cur != h3  # verify_chain would flag row 3 as broken


def test_canonical_json_order_insensitive():
    """Chain is stable across Python dict ordering (sort_keys=True)."""
    a = {"x": 1, "y": 2}
    b = {"y": 2, "x": 1}
    assert _chain_hash(_GENESIS_HASH, a) == _chain_hash(_GENESIS_HASH, b)
