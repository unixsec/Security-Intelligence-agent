"""SEC-3: PKCE — authorization URL must contain ``code_challenge``
and ``code_challenge_method=S256``; the verifier must be reusable
(via ``state``) on callback exactly once.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import pytest


@pytest.fixture
def fake_oidc_cfg():
    return {
        "oidc": {
            "enabled": True,
            "providers": {
                "test": {
                    "issuer": "https://idp.example.com",
                    "client_id": "client-x",
                    "client_secret": "secret-x",
                }
            },
        }
    }


@pytest.mark.asyncio
async def test_authorize_url_contains_pkce(fake_oidc_cfg):
    fake_discovery = {
        "authorization_endpoint": "https://idp.example.com/oauth2/authorize",
        "token_endpoint": "https://idp.example.com/oauth2/token",
        "userinfo_endpoint": "https://idp.example.com/userinfo",
    }
    with patch("sia.config.get_auth_config", return_value=fake_oidc_cfg):
        from sia.auth.providers.oidc import OIDCProvider

        prov = OIDCProvider()
        prov._discover = AsyncMock(return_value=fake_discovery)

        url = await prov.get_authorization_url("test", "https://app/callback", "state-xyz")
        params = parse_qs(urlparse(url).query)

        assert params.get("code_challenge_method") == ["S256"]
        ch = params.get("code_challenge")
        assert ch and len(ch[0]) >= 43  # base64url(sha256) = 43 chars

    # The verifier should be stored under the state for the callback.
    assert prov._pop_verifier("state-xyz") is not None


@pytest.mark.asyncio
async def test_callback_without_state_rejected(fake_oidc_cfg):
    with patch("sia.config.get_auth_config", return_value=fake_oidc_cfg):
        from sia.auth.providers.oidc import OIDCProvider

        prov = OIDCProvider()
        prov._discover = AsyncMock(return_value={
            "authorization_endpoint": "x", "token_endpoint": "y", "userinfo_endpoint": "z"
        })

        # Unknown state -> verifier missing -> ValueError.
        with pytest.raises(ValueError):
            await prov.handle_callback("test", "https://app/callback", "code1", state="never-issued")
