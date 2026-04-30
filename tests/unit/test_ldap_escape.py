"""SEC-1: LDAPProvider must escape RFC 4515 special characters before
substituting the username into the search filter.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


def test_username_metachars_are_escaped(monkeypatch):
    """An attacker-controlled username with `*)(uid=*` must NOT inject
    a wildcard into the LDAP search filter.
    """
    fake_cfg = {
        "ldap": {
            "enabled": True,
            "server": "ldap://example.com",
            "bind_dn": "cn=svc,dc=example,dc=com",
            "bind_password": "x",
            "user_search_base": "dc=example,dc=com",
            "user_search_filter": "(sAMAccountName={username})",
        }
    }

    # Patch get_auth_config before importing LDAPProvider so __init__ sees it.
    with patch("sia.config.get_auth_config", return_value=fake_cfg):
        from sia.auth.providers.ldap import LDAPProvider, escape_filter_chars

    raw = "*)(uid=*"
    safe = escape_filter_chars(raw)
    assert "*" not in safe.replace(r"\2a", "")
    # Make sure ldap3's escape returns the canonical RFC 4515 hex form.
    assert r"\2a" in safe
    assert r"\28" in safe
    assert r"\29" in safe


def test_authenticate_rejects_pathological_input(monkeypatch):
    fake_cfg = {
        "ldap": {
            "enabled": True,
            "server": "ldap://example.com",
            "bind_dn": "cn=svc,dc=example,dc=com",
            "bind_password": "x",
            "user_search_base": "dc=example,dc=com",
        }
    }
    with patch("sia.config.get_auth_config", return_value=fake_cfg):
        from sia.auth.providers.ldap import LDAPProvider

        prov = LDAPProvider()
        with pytest.raises(ValueError):
            prov.authenticate("a" * 1024, "p")  # username too long
        with pytest.raises(ValueError):
            prov.authenticate("alice", "p" * 5000)  # password too long
        with pytest.raises(ValueError):
            prov.authenticate("", "p")  # empty username
