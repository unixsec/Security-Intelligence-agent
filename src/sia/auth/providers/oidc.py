"""OpenID Connect federation provider.

Supports any OIDC-compliant IdP: Azure AD, Keycloak, Okta, Google Workspace, etc.
Uses authlib for the protocol layer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.oidc.core import CodeIDToken

from sia.config import get_auth_config

logger = logging.getLogger(__name__)


@dataclass
class OIDCUserInfo:
    """Normalized user info from any OIDC provider."""
    external_id: str       # sub claim
    email: str
    display_name: str
    username: str
    issuer: str
    provider_key: str      # config key (e.g. "azure", "keycloak")
    role: str | None       # mapped role, if role_claim configured
    raw_claims: dict


class OIDCProvider:
    """Manages multiple OIDC providers from config."""

    def __init__(self) -> None:
        cfg = get_auth_config().get("oidc", {})
        self.enabled: bool = cfg.get("enabled", False)
        self._providers: dict[str, dict] = cfg.get("providers", {}) or {}
        # Discovery document cache
        self._discovery: dict[str, dict] = {}

    def list_providers(self) -> list[dict]:
        """Return available providers for frontend login page."""
        return [
            {"key": k, "display_name": v.get("display_name", k)}
            for k, v in self._providers.items()
        ]

    def get_provider_config(self, key: str) -> dict:
        if key not in self._providers:
            raise ValueError(f"Unknown OIDC provider: {key}")
        return self._providers[key]

    async def _discover(self, issuer: str) -> dict:
        """Fetch OIDC discovery document (cached)."""
        if issuer in self._discovery:
            return self._discovery[issuer]

        url = f"{issuer.rstrip('/')}/.well-known/openid-configuration"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            doc = resp.json()
            self._discovery[issuer] = doc
            return doc

    async def get_authorization_url(
        self, provider_key: str, redirect_uri: str, state: str
    ) -> str:
        """Build the authorization URL to redirect the user to the IdP."""
        pcfg = self.get_provider_config(provider_key)
        discovery = await self._discover(pcfg["issuer"])

        client = AsyncOAuth2Client(
            client_id=pcfg["client_id"],
            client_secret=pcfg.get("client_secret"),
            scope=" ".join(pcfg.get("scopes", ["openid", "profile", "email"])),
            redirect_uri=redirect_uri,
        )
        url, _ = client.create_authorization_url(
            discovery["authorization_endpoint"],
            state=state,
        )
        return url

    async def handle_callback(
        self, provider_key: str, redirect_uri: str, code: str
    ) -> OIDCUserInfo:
        """Exchange authorization code for tokens and extract user info."""
        pcfg = self.get_provider_config(provider_key)
        discovery = await self._discover(pcfg["issuer"])

        client = AsyncOAuth2Client(
            client_id=pcfg["client_id"],
            client_secret=pcfg.get("client_secret"),
            redirect_uri=redirect_uri,
        )

        # Exchange code for tokens
        token = await client.fetch_token(
            discovery["token_endpoint"],
            code=code,
        )

        # Fetch userinfo
        async with httpx.AsyncClient(timeout=10) as http:
            resp = await http.get(
                discovery["userinfo_endpoint"],
                headers={"Authorization": f"Bearer {token['access_token']}"},
            )
            resp.raise_for_status()
            claims = resp.json()

        # Map role if configured
        mapped_role = self._map_role(pcfg, claims)

        # Build normalized user info
        email = claims.get("email", "")
        return OIDCUserInfo(
            external_id=claims.get("sub", ""),
            email=email,
            display_name=claims.get("name", email.split("@")[0]),
            username=claims.get("preferred_username", email.split("@")[0]),
            issuer=pcfg["issuer"],
            provider_key=provider_key,
            role=mapped_role,
            raw_claims=claims,
        )

    def _map_role(self, pcfg: dict, claims: dict) -> str | None:
        """Extract role from OIDC claims using configured mapping."""
        role_claim = pcfg.get("role_claim")
        role_mapping = pcfg.get("role_mapping", {})

        if not role_claim or not role_mapping:
            return pcfg.get("default_role", "viewer")

        # Navigate nested claim (e.g. "realm_access.roles")
        value = claims
        for part in role_claim.split("."):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                break

        if not value:
            return pcfg.get("default_role", "viewer")

        # value can be a list of roles or a single string
        roles = value if isinstance(value, list) else [value]
        for idp_role, sia_role in role_mapping.items():
            if idp_role in roles:
                return sia_role

        return pcfg.get("default_role", "viewer")

    @property
    def auto_create_enabled(self) -> bool:
        return any(p.get("auto_create_user", True) for p in self._providers.values())


# Module-level singleton
_oidc_provider: OIDCProvider | None = None


def get_oidc_provider() -> OIDCProvider:
    global _oidc_provider
    if _oidc_provider is None:
        _oidc_provider = OIDCProvider()
    return _oidc_provider
