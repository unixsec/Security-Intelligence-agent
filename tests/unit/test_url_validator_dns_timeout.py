"""SEC-5: DNS resolution must time out so a malicious resolver cannot
hang the collector indefinitely.
"""
from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from sia.collector import url_validator


def _hung_getaddrinfo(*_a, **_k):
    """Simulate a slow / hanging resolver via socket.timeout (the wrapped
    socket.setdefaulttimeout will surface a timeout instead of blocking)."""
    raise socket.timeout("DNS hang")


def test_dns_timeout_surfaces_as_unsafe_url():
    with patch.object(url_validator.socket, "getaddrinfo", _hung_getaddrinfo):
        with pytest.raises(url_validator.UnsafeURLError):
            url_validator.validate_source_url("https://slow-resolver.example/")


def test_dns_constant_is_set():
    # Sanity: the constant is in the right ballpark, not 60s or 0.
    assert 1.0 <= url_validator._DNS_TIMEOUT_SEC <= 10.0
