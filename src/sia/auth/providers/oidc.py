"""OpenID Connect federation provider.

Supports any OIDC-compliant IdP: Azure AD, Keycloak, Okta, Google Workspace, etc.
Uses authlib for the protocol layer.

SEC-3: PKCE (RFC 7636) is REQUIRED for the public-client / browser leg.
We always send ``code_challenge_method=S256``; the verifier is held in a
short-TTL in-process map keyed by ``state``. For multi-replica deployments
that need state persistence across pods, swap the map for a Redis-backed
store (one-line change in ``_verifier_store``).
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import time
from dataclasses import dataclass

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.oidc.core import CodeIDToken

from sia.config import get_auth_config

logger = logging.getLogger(__name__)

# PKCE verifier TTL — RFC 7636 expects code exchange to happen within minutes.
_PKCE_VERIFIER_TTL_SEC = 600


def _pkce_pair() -> tuple[str, str]:
    """Return (verifier, S256 challenge). RFC 7636 §4.1/§4.2."""
    verifier = secrets.token_urlsafe(64)[:128]   # 43..128 chars, base64url
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


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
        # PKCE verifier store: state -> (verifier, expires_at_epoch).
        # Single-process; replace with Redis for multi-replica.
        self._verifiers: dict[str, tuple[str, float]] = {}

    def _put_verifier(self, state: str, verifier: str) -> None:
        # Lazy GC of expired entries (cheap: dozens of items at most).
        now = time.time()
        if len(self._verifiers) > 1024:
            self._verifiers = {
                k: v for k, v in self._verifiers.items() if v[1] > now
            }
        self._verifiers[state] = (verifier, now + _PKCE_VERIFIER_TTL_SEC)

    def _pop_verifier(self, state: str) -> str | None:
        entry = self._verifiers.pop(state, None)
        if not entry:
            return None
        verifier, exp = entry
        if exp < time.time():
            return None
        return verifier

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
        """Build the authorization URL to redirect the user to the IdP.

        SEC-3: emits ``code_challenge`` + ``code_challenge_method=S256``.
        The matching verifier is stored under ``state`` and consumed in
        ``handle_callback``.
        """
        pcfg = self.get_provider_config(provider_key)
        discovery = await self._discover(pcfg["issuer"])

        verifier, challenge = _pkce_pair()
        self._put_verifier(state, verifier)

        client = AsyncOAuth2Client(
            client_id=pcfg["client_id"],
            client_secret=pcfg.get("client_secret"),
            scope=" ".join(pcfg.get("scopes", ["openid", "profile", "email"])),
            redirect_uri=redirect_uri,
        )
        url, _ = client.create_authorization_url(
            discovery["authorization_endpoint"],
            state=state,
            code_challenge=challenge,
            code_challenge_method="S256",
        )
        return url

    async def handle_callback(
        self, provider_key: str, redirect_uri: str, code: str, state: str | None = None
    ) -> OIDCUserInfo:
        """Exchange authorization code for tokens and extract user info.

        ``state`` is required when PKCE was used during the redirect (it always
        is, post-SEC-3). For backwards compatibility we tolerate ``None`` but
        log a warning — production deployments should always pass it.
        """
        pcfg = self.get_provider_config(provider_key)
        discovery = await self._discover(pcfg["issuer"])

        client = AsyncOAuth2Client(
            client_id=pcfg["client_id"],
            client_secret=pcfg.get("client_secret"),
            redirect_uri=redirect_uri,
        )

        verifier: str | None = None
        if state:
            verifier = self._pop_verifier(state)
            if verifier is None:
                # Either CSRF, replay, or expired — refuse rather than
                # exchange the code without PKCE.
                raise ValueError("OIDC state expired or unknown; restart login")
        else:
            logger.warning("OIDC handle_callback called without state; PKCE skipped")

        token_kwargs: dict = {"code": code}
        if verifier is not None:
            token_kwargs["code_verifier"] = verifier

        # Exchange code for tokens
        token = await client.fetch_token(
            discovery["token_endpoint"],
            **token_kwargs,
        )

        # Fetch userinfo
        async with httpx.AsyncClient(timeout=10) as http:
            resp = await http.get(
                discovery["userinfo_endpoint"],
                headers={"Authorization": f"Bearer {token['access_token']}"},
            )
            if resp.status_code >= 400:
                raise ValueError(
                    f"OIDC userinfo endpoint returned {resp.status_code}: "
                    f"{resp.text[:200]!r}"
                )
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
