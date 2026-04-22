"""LDAP / Active Directory authentication provider.

Uses ldap3 (pure-Python, no system libldap dependency).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import ldap3
from ldap3 import ALL, SUBTREE, Connection, Server
from ldap3.core.exceptions import LDAPBindError, LDAPException

from sia.config import get_auth_config

logger = logging.getLogger(__name__)


@dataclass
class LDAPUserInfo:
    """Normalized user info from LDAP/AD."""
    external_id: str       # DN
    username: str
    email: str
    display_name: str
    groups: list[str]      # Group DNs
    role: str              # Mapped SIA role


class LDAPProvider:
    """LDAP/AD bind-and-search authentication."""

    def __init__(self) -> None:
        cfg = get_auth_config().get("ldap", {})
        self.enabled: bool = cfg.get("enabled", False)
        self._cfg = cfg

    def authenticate(self, username: str, password: str) -> LDAPUserInfo:
        """Bind as service account, search user, re-bind to verify password.

        Raises ValueError on auth failure.
        """
        cfg = self._cfg
        if not self.enabled:
            raise ValueError("LDAP authentication is not enabled")

        server = Server(
            cfg["server"],
            use_ssl=cfg.get("use_ssl", False),
            get_info=ALL,
        )

        # Step 1: Bind with service account. If StartTLS is requested it
        # must be negotiated on the anonymous connection BEFORE the bind,
        # otherwise credentials travel in cleartext and the TLS upgrade
        # is a no-op.
        use_start_tls = cfg.get("start_tls", False)
        try:
            svc_conn = Connection(
                server,
                user=cfg["bind_dn"],
                password=cfg["bind_password"],
                auto_bind=False,
            )
            if use_start_tls and not svc_conn.start_tls():
                raise LDAPException("StartTLS negotiation failed")
            if not svc_conn.bind():
                raise LDAPBindError("bind returned False")
        except (LDAPBindError, LDAPException):
            logger.error("LDAP service account bind failed")
            raise ValueError("LDAP service unavailable")

        # Step 2: Search for the user
        search_filter = cfg.get(
            "user_search_filter", "(sAMAccountName={username})"
        ).format(username=username)

        username_attr = cfg.get("username_attribute", "sAMAccountName")
        email_attr = cfg.get("email_attribute", "mail")
        display_attr = cfg.get("display_name_attribute", "displayName")

        svc_conn.search(
            search_base=cfg["user_search_base"],
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=[username_attr, email_attr, display_attr, "memberOf"],
        )

        if not svc_conn.entries:
            svc_conn.unbind()
            raise ValueError("User not found in directory")

        entry = svc_conn.entries[0]
        user_dn = str(entry.entry_dn)
        svc_conn.unbind()

        # Step 3: Re-bind as the user to verify password. StartTLS again so
        # the user's password is not sent in cleartext.
        try:
            user_conn = Connection(server, user=user_dn, password=password, auto_bind=False)
            if use_start_tls and not user_conn.start_tls():
                raise LDAPException("StartTLS negotiation failed")
            if not user_conn.bind():
                raise LDAPBindError("user bind returned False")
            user_conn.unbind()
        except (LDAPBindError, LDAPException):
            raise ValueError("Invalid credentials")

        # Step 4: Extract attributes
        groups = [str(g) for g in entry.memberOf.values] if hasattr(entry, "memberOf") and entry.memberOf else []

        return LDAPUserInfo(
            external_id=user_dn,
            username=str(getattr(entry, username_attr, username)),
            email=str(getattr(entry, email_attr, "")),
            display_name=str(getattr(entry, display_attr, username)),
            groups=groups,
            role=self._map_role(groups),
        )

    def _map_role(self, groups: list[str]) -> str:
        """Map LDAP groups to SIA role."""
        role_mapping = self._cfg.get("role_mapping", {})
        for group_dn, sia_role in role_mapping.items():
            if group_dn in groups:
                return sia_role
        return self._cfg.get("default_role", "viewer")


_ldap_provider: LDAPProvider | None = None


def get_ldap_provider() -> LDAPProvider:
    global _ldap_provider
    if _ldap_provider is None:
        _ldap_provider = LDAPProvider()
    return _ldap_provider
