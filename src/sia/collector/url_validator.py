"""URL 安全校验 — 拦截 SSRF 风险目标 (CRIT from ARCHITECTURE_REVIEW §B-1).

情报源 URL 由运维在数据库里配置。若管理员账号被接管（或误操作），
攻击者可把 source.url 指向内网端点（127.0.0.1:6379 → Redis、
169.254.169.254 → 云 metadata），然后让 Collector 代为访问。

本模块在每次抓取前解析并校验 URL：
  - 仅允许 http / https
  - 解析目标主机到 IP，拒绝回环、RFC1918、link-local 等内网段
  - URL 总长、主机长、最大重定向都有上限

fetcher 侧同时须关闭 `follow_redirects`（或在每次跳转后重新校验），
见 `sia.collector.fetcher.BaseFetcher._get_http_client`。
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_MAX_URL_LEN = 2048
_MAX_HOST_LEN = 253

# SEC-5: cap DNS resolution time. ``getaddrinfo`` can hang indefinitely on a
# malicious or slow resolver; a single hung call would block the consumer
# thread until the request layer gives up. 5 seconds is more than enough for
# a healthy resolver and short enough to fail fast under attack.
_DNS_TIMEOUT_SEC = 5.0

# 默认拒绝的网段（IPv4 + IPv6）。链路本地 169.254.0.0/16 覆盖了
# AWS / GCP / Azure 的 instance metadata (169.254.169.254)。
_DENY_NETS: tuple[ipaddress._BaseNetwork, ...] = tuple(
    ipaddress.ip_network(n)
    for n in (
        "0.0.0.0/8",
        "10.0.0.0/8",
        "100.64.0.0/10",       # Carrier-grade NAT (AWS shared)
        "127.0.0.0/8",         # loopback
        "169.254.0.0/16",      # link-local (cloud metadata)
        "172.16.0.0/12",
        "192.0.0.0/24",
        "192.168.0.0/16",
        "198.18.0.0/15",       # benchmarking
        "224.0.0.0/4",         # multicast
        "240.0.0.0/4",         # reserved
        "::/128",              # unspecified
        "::1/128",             # loopback v6
        "fc00::/7",            # unique local v6
        "fe80::/10",           # link-local v6
        "ff00::/8",             # multicast v6
    )
)


class UnsafeURLError(ValueError):
    """URL 指向内网/本地/非法 scheme/格式错误等不安全目标。"""


def validate_source_url(url: str, *, allowed_hosts: set[str] | None = None) -> None:
    """Raise UnsafeURLError if url targets internal / loopback / metadata endpoints.

    Args:
        url: 待校验的完整 URL。
        allowed_hosts: 可选的主机白名单。若提供，则 URL 的 hostname 必须在其中。

    Behavior:
        - 长度、scheme 快速拒绝
        - DNS 解析一次，对返回的每个 A / AAAA 结果逐一检查
        - 若 host 已经是 IP 字面量，直接检查
        - 调用方同时须关闭跟随重定向（或跳转后重新调本函数）
    """
    if not url or len(url) > _MAX_URL_LEN:
        raise UnsafeURLError(f"URL missing or too long (> {_MAX_URL_LEN})")

    p = urlparse(url)
    if p.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeURLError(f"scheme {p.scheme!r} not allowed (must be http/https)")

    host = p.hostname
    if not host:
        raise UnsafeURLError("missing hostname")
    if len(host) > _MAX_HOST_LEN:
        raise UnsafeURLError(f"hostname too long (> {_MAX_HOST_LEN})")

    if allowed_hosts is not None and host not in allowed_hosts:
        raise UnsafeURLError(f"host {host!r} not in allowlist")

    # 若 host 本身是 IP 字面量，直接校验；否则 DNS 解析（带超时）。
    addrs: set[str] = set()
    try:
        ipaddress.ip_address(host)
        addrs.add(host)
    except ValueError:
        # SEC-5: enforce a hard timeout on the resolver via socket-level
        # default. ``setdefaulttimeout`` is process-global; we restore the
        # previous value after the call.
        prev_to = socket.getdefaulttimeout()
        socket.setdefaulttimeout(_DNS_TIMEOUT_SEC)
        try:
            # getaddrinfo 返回 [(family, type, proto, canon, sockaddr), ...]
            # sockaddr[0] 是 IP 字符串
            results = socket.getaddrinfo(host, None)
        except (OSError, socket.timeout) as e:
            raise UnsafeURLError(f"DNS resolution failed for {host!r}: {e}") from e
        finally:
            socket.setdefaulttimeout(prev_to)
        addrs = {r[4][0] for r in results}

    if not addrs:
        raise UnsafeURLError(f"no addresses resolved for {host!r}")

    for a in addrs:
        try:
            ip = ipaddress.ip_address(a.split("%")[0])  # strip scope id if any
        except ValueError:
            continue
        for net in _DENY_NETS:
            if ip in net:
                raise UnsafeURLError(
                    f"URL {url!r} resolves to internal/blocked address {ip} "
                    f"(matched {net})"
                )


def is_safe_source_url(url: str, *, allowed_hosts: set[str] | None = None) -> bool:
    """Boolean variant of validate_source_url — never raises."""
    try:
        validate_source_url(url, allowed_hosts=allowed_hosts)
    except UnsafeURLError:
        return False
    return True
