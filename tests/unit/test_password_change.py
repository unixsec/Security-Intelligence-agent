"""Unit tests for first-login password change policy (ARCHITECTURE_REVIEW §B-7)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from sia.gateway.api.v1.auth import _assert_password_policy


class TestPasswordPolicy:
    """Enforce the configured complexity rules at change-password time."""

    def test_too_short_rejected(self):
        with pytest.raises(HTTPException) as exc:
            _assert_password_policy("Short1!", {"min_length": 12})
        assert "at least 12" in exc.value.detail

    def test_requires_uppercase(self):
        with pytest.raises(HTTPException, match="uppercase"):
            _assert_password_policy("alllower1", {"min_length": 8, "require_uppercase": True})

    def test_requires_lowercase(self):
        with pytest.raises(HTTPException, match="lowercase"):
            _assert_password_policy("ALLUPPER1", {"min_length": 8, "require_lowercase": True})

    def test_requires_digit(self):
        with pytest.raises(HTTPException, match="digit"):
            _assert_password_policy("NoDigitsHere", {"min_length": 8, "require_digit": True})

    def test_requires_special(self):
        with pytest.raises(HTTPException, match="special"):
            _assert_password_policy("Nothing1Here",
                                    {"min_length": 8, "require_special": True})

    def test_compliant_password_passes(self):
        # Should not raise
        _assert_password_policy("Compliant1Pass!", {
            "min_length": 12,
            "require_uppercase": True,
            "require_lowercase": True,
            "require_digit": True,
            "require_special": True,
        })

    def test_relaxed_policy_accepts_short(self):
        _assert_password_policy("ab12", {
            "min_length": 4,
            "require_uppercase": False,
            "require_lowercase": False,
            "require_digit": False,
            "require_special": False,
        })

    def test_special_chars_list(self):
        """The set of accepted special characters is broad enough for common use."""
        for c in "!@#$%^&*()-_=+":
            _assert_password_policy(f"Aa1{c}aaaa", {
                "min_length": 8, "require_uppercase": True,
                "require_lowercase": True, "require_digit": True,
                "require_special": True,
            })
