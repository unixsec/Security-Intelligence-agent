"""Unit tests for SSRF-safe URL validator (ARCHITECTURE_REVIEW §E.1)."""

from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from sia.collector.url_validator import (
    UnsafeURLError,
    is_safe_source_url,
    validate_source_url,
)


class TestSchemeAndFormat:
    def test_missing_url(self):
        with pytest.raises(UnsafeURLError, match="missing"):
            validate_source_url("")

    def test_too_long(self):
        with pytest.raises(UnsafeURLError, match="too long"):
            validate_source_url("https://a.example.com/" + "x" * 5000)

    @pytest.mark.parametrize("scheme", ["file", "gopher", "ftp", "javascript", "data"])
    def test_disallowed_scheme(self, scheme):
        with pytest.raises(UnsafeURLError, match="scheme"):
            validate_source_url(f"{scheme}://example.com/")

    def test_missing_host(self):
        with pytest.raises(UnsafeURLError, match="hostname"):
            validate_source_url("https:///path")


class TestIPLiteralBlocking:
    """Pure IP literals never hit DNS, so we exercise the deny nets directly."""

    @pytest.mark.parametrize("url", [
        "http://127.0.0.1/",
        "http://127.0.0.1:8080/api",
        "https://10.0.0.5/",
        "https://10.211.55.8/",
        "https://172.16.0.1/",
        "https://192.168.1.100/",
        "https://169.254.169.254/latest/meta-data/",  # AWS metadata
        "https://169.254.170.2/",                     # ECS task metadata
        "http://0.0.0.0/",
        "http://[::1]/",
    ])
    def test_blocked_internal_ip(self, url):
        with pytest.raises(UnsafeURLError, match="internal|blocked"):
            validate_source_url(url)


class TestDNSResolutionBlocking:
    """Hostname that resolves to internal IP is blocked."""

    def test_dns_to_loopback_blocked(self):
        with patch(
            "sia.collector.url_validator.socket.getaddrinfo",
            return_value=[(2, 1, 0, "", ("127.0.0.1", 0))],
        ):
            with pytest.raises(UnsafeURLError, match="internal|blocked"):
                validate_source_url("https://attacker.example.com/")

    def test_dns_to_metadata_blocked(self):
        with patch(
            "sia.collector.url_validator.socket.getaddrinfo",
            return_value=[(2, 1, 0, "", ("169.254.169.254", 0))],
        ):
            with pytest.raises(UnsafeURLError, match="internal|blocked"):
                validate_source_url("https://dns-rebind.example.com/")

    def test_dns_to_public_ip_ok(self):
        with patch(
            "sia.collector.url_validator.socket.getaddrinfo",
            return_value=[(2, 1, 0, "", ("93.184.216.34", 0))],
        ):
            validate_source_url("https://example.com/feed.xml")  # no raise

    def test_dns_fail_rejects(self):
        with patch(
            "sia.collector.url_validator.socket.getaddrinfo",
            side_effect=socket.gaierror("no such host"),
        ):
            with pytest.raises(UnsafeURLError, match="DNS"):
                validate_source_url("https://nx.example.invalid/")

    def test_any_ip_in_response_blocks(self):
        """Multi-homed target: if ANY resolved IP is internal, reject."""
        with patch(
            "sia.collector.url_validator.socket.getaddrinfo",
            return_value=[
                (2, 1, 0, "", ("93.184.216.34", 0)),   # public
                (2, 1, 0, "", ("10.0.0.5", 0)),        # internal — must block
            ],
        ):
            with pytest.raises(UnsafeURLError, match="internal|blocked"):
                validate_source_url("https://multihomed.example.com/")


class TestAllowlist:
    def test_allowed_host_passes(self):
        with patch(
            "sia.collector.url_validator.socket.getaddrinfo",
            return_value=[(2, 1, 0, "", ("93.184.216.34", 0))],
        ):
            validate_source_url(
                "https://trusted.example.com/feed",
                allowed_hosts={"trusted.example.com"},
            )  # no raise

    def test_not_allowed_host_blocked(self):
        with pytest.raises(UnsafeURLError, match="allowlist"):
            validate_source_url(
                "https://other.example.com/feed",
                allowed_hosts={"trusted.example.com"},
            )


class TestIsSafeHelper:
    def test_never_raises_on_unsafe(self):
        assert is_safe_source_url("http://127.0.0.1/") is False

    def test_returns_true_on_safe(self):
        with patch(
            "sia.collector.url_validator.socket.getaddrinfo",
            return_value=[(2, 1, 0, "", ("93.184.216.34", 0))],
        ):
            assert is_safe_source_url("https://example.com/") is True
