"""Tests for deduplication logic."""

from sia.analyzer.dedup import compute_fingerprint


class TestFingerprint:
    def test_consistent_hash(self):
        fp1 = compute_fingerprint("Test Title", "https://example.com/1")
        fp2 = compute_fingerprint("Test Title", "https://example.com/1")
        assert fp1 == fp2

    def test_case_insensitive(self):
        fp1 = compute_fingerprint("Test Title", "https://example.com/1")
        fp2 = compute_fingerprint("test title", "HTTPS://EXAMPLE.COM/1")
        assert fp1 == fp2

    def test_whitespace_normalized(self):
        fp1 = compute_fingerprint("  Test Title  ", "https://example.com/1")
        fp2 = compute_fingerprint("Test Title", "https://example.com/1")
        assert fp1 == fp2

    def test_different_inputs_different_hash(self):
        fp1 = compute_fingerprint("Title A", "https://example.com/1")
        fp2 = compute_fingerprint("Title B", "https://example.com/1")
        assert fp1 != fp2

    def test_sha256_length(self):
        fp = compute_fingerprint("Test", "https://test.com")
        assert len(fp) == 64  # SHA-256 hex digest
