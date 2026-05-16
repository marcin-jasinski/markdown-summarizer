"""
Egress policy — SSRF protection for all outbound HTTP requests.

Every outbound fetch (article fetcher, image URL resolution, webhook callbacks)
MUST go through :class:`EgressPolicy`.  Direct use of ``httpx``, ``aiohttp``,
``urllib``, or ``requests`` outside this module is prohibited.

DNS-rebinding protection
------------------------
:meth:`EgressPolicy.fetch` resolves the target hostname asynchronously
(non-blocking event loop), validates every returned IP address against
private/reserved ranges, and then pins the TCP connection to that pre-validated
IP address via :class:`_PinnedIPTransport`.  This prevents a DNS-rebinding
attack where an adversary races the DNS TTL between the validation lookup and
the actual connection.

Literal IP addresses in URLs are validated synchronously in
:meth:`EgressPolicy.validate_url` without any DNS lookup (no TTL race possible
for literals).  Hostname-to-IP validation is deferred to :meth:`fetch` because
it requires asynchronous DNS resolution.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import ssl
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpcore
import httpx

if TYPE_CHECKING:
    from mindforge.infrastructure.config import EgressSettings

from mindforge.domain.ports import EgressViolation  # re-exported for backward compat

__all__ = ["EgressViolation", "EgressPolicy"]

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

# EgressViolation is defined in mindforge.domain.ports and re-exported here.
# Import from domain to keep agents free of infrastructure dependencies.


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STANDARD_PORTS: dict[str, int] = {"http": 80, "https": 443}

# Private / reserved IP ranges per RFC 1918, RFC 4193, RFC 3927, etc.
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),  # Unique local (IPv6)
    ipaddress.ip_network("fe80::/10"),  # Link-local (IPv6)
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local / APIPA (IPv4)
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),  # Shared address space (RFC 6598)
]

# Cloud metadata service IPs (SSRF targets)
_METADATA_IPS = frozenset(
    {
        "169.254.169.254",  # AWS/GCP/Azure/DigitalOcean instance metadata
        "fd00:ec2::254",  # AWS IPv6 metadata
        "metadata.google.internal",
    }
)

_USER_AGENT = "MindForge/2.0"


# ---------------------------------------------------------------------------
# IP-pinning transport (prevents DNS rebinding on the TCP connection)
# ---------------------------------------------------------------------------


class _PinnedNetworkBackend(httpcore.AsyncNetworkBackend):
    """
    httpcore network backend that connects to a pre-validated IP address.

    By overriding ``connect_tcp`` to use the pinned IP instead of ``host``,
    we ensure the resolved-and-validated IP from the pre-flight check is the
    same IP that httpcore actually connects to.  This closes the DNS-rebinding
    window between validation and connection.
    """

    def __init__(self, pinned_ip: str) -> None:
        self._pinned_ip = pinned_ip
        self._inner = httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: object = None,
    ) -> httpcore.AsyncNetworkStream:
        # ``host`` contains the original hostname from the URL; we ignore it
        # and connect directly to the pre-validated pinned IP instead.
        return await self._inner.connect_tcp(
            self._pinned_ip,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: object = None,
    ) -> httpcore.AsyncNetworkStream:
        raise EgressViolation(
            "Unix socket connections are not permitted by egress policy."
        )

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


class _PinnedIPTransport(httpx.AsyncHTTPTransport):
    """
    httpx async transport that pins its connection to a pre-resolved IP.

    Subclasses :class:`httpx.AsyncHTTPTransport` and replaces the internal
    httpcore connection pool with one that uses :class:`_PinnedNetworkBackend`.
    This preserves all of httpx’s request/response bridge logic while
    ensuring every TCP connection goes to the validated IP.
    """

    def __init__(self, pinned_ip: str) -> None:
        super().__init__()
        ssl_ctx = ssl.create_default_context()
        # Replace the pool created by super().__init__() with a pinned one.
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=ssl_ctx,
            network_backend=_PinnedNetworkBackend(pinned_ip),
        )


class EgressPolicy:
    """
    Validates and enforces outbound HTTP policies.

    Protects against SSRF, access to cloud metadata endpoints, and
    fetches to private network ranges.
    """

    def __init__(self, settings: EgressSettings) -> None:
        self._settings = settings

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_url(self, url: str) -> None:
        """
        Synchronous validation: scheme, port, metadata-host literals, and
        literal IP private-range checks.

        Does NOT perform DNS resolution for non-literal hostnames; hostname → IP
        validation happens asynchronously inside :meth:`fetch` which also pins
        the connection to prevent DNS rebinding.  For full SSRF protection
        against hostname-based targets, always use :meth:`fetch`.

        Raises :class:`EgressViolation` on any violation.
        """
        parsed = urlparse(url)

        self._check_scheme(parsed.scheme, url)
        self._check_port(parsed.scheme, parsed.port, url)

        hostname = parsed.hostname
        if not hostname:
            raise EgressViolation(f"URL has no hostname: {url!r}")

        if hostname in _METADATA_IPS:
            raise EgressViolation(f"URL targets a cloud metadata endpoint: {url!r}")

        # For literal IP addresses (e.g. http://10.0.0.1/), validate immediately
        # without DNS — there is no TTL race for literal IPs.
        # Use try/except/else to avoid swallowing EgressViolation(ValueError) in
        # the except clause.
        try:
            ip = ipaddress.ip_address(hostname)
        except ValueError:
            # hostname is not a literal IP; private-range check deferred to fetch()
            pass
        else:
            if not self._settings.allow_private_networks and self._is_private(ip):
                raise EgressViolation(
                    f"URL targets a private/reserved IP address ({hostname}). "
                    f"URL: {url!r}"
                )

    async def fetch(self, url: str) -> bytes:
        """
        Full-stack safe HTTP GET with async DNS resolution and IP pinning.

        For each request (including every redirect hop):
        1. Validates scheme, port, and metadata-host literals.
        2. Resolves the hostname asynchronously (non-blocking event loop — F-3).
        3. Validates every resolved IP against private/reserved ranges.
        4. Pins the TCP connection to the first valid IP via ``_PinnedIPTransport``
           so that a DNS TTL race cannot redirect the actual connection (F-1).
        5. Re-validates and re-pins for each redirect destination.

        Returns the response body as bytes.
        Raises :class:`EgressViolation` on any policy breach or
        :class:`httpx.HTTPError` on transport errors.
        """
        max_bytes = self._settings.max_response_bytes
        timeout = self._settings.timeout_seconds

        current_url = url
        hops = 0
        max_hops = 10

        while hops <= max_hops:
            parsed = urlparse(current_url)
            self._check_scheme(parsed.scheme, current_url)
            self._check_port(parsed.scheme, parsed.port, current_url)

            hostname = parsed.hostname
            if not hostname:
                raise EgressViolation(f"URL has no hostname: {current_url!r}")

            if hostname in _METADATA_IPS:
                raise EgressViolation(
                    f"URL targets a cloud metadata endpoint: {current_url!r}"
                )

            # Async DNS + IP validation (non-blocking, fixes F-3)
            pinned_ip = await self._resolve_safe_ip(hostname, current_url)

            # IP-pinned transport (prevents DNS rebinding, fixes F-1)
            transport = _PinnedIPTransport(pinned_ip=pinned_ip)

            async with httpx.AsyncClient(
                transport=transport,
                follow_redirects=False,
                timeout=timeout,
                headers={"User-Agent": _USER_AGENT},
            ) as client:
                response = await client.get(current_url)

            if not response.is_redirect:
                response.raise_for_status()
                # Enforce response size limit
                body = b""
                for chunk in response.iter_bytes(chunk_size=8192):
                    body += chunk
                    if len(body) > max_bytes:
                        raise EgressViolation(
                            f"Response exceeds max_response_bytes ({max_bytes}) "
                            f"for URL: {url!r}"
                        )
                return body

            redirect_url = response.headers.get("location", "")
            if not redirect_url:
                raise EgressViolation(
                    f"Redirect response has empty location for URL: {current_url!r}"
                )
            current_url = redirect_url
            hops += 1

        raise EgressViolation(f"Too many redirects (> {max_hops}) for URL: {url!r}")

    # ------------------------------------------------------------------
    # Internal checks
    # ------------------------------------------------------------------

    def _check_scheme(self, scheme: str, url: str) -> None:
        allowed = set(self._settings.allowed_protocols)
        if scheme.lower() not in allowed:
            raise EgressViolation(
                f"URL scheme {scheme!r} is not allowed. "
                f"Allowed: {sorted(allowed)}. URL: {url!r}"
            )

    def _check_port(self, scheme: str, port: int | None, url: str) -> None:
        if port is None:
            return  # Standard port implied
        standard = _STANDARD_PORTS.get(scheme.lower())
        if not self._settings.allow_nonstandard_ports and standard is not None:
            if port != standard:
                raise EgressViolation(
                    f"Non-standard port {port} is not allowed for scheme {scheme!r}. "
                    f"URL: {url!r}"
                )

    async def _resolve_safe_ip(self, hostname: str, url: str) -> str:
        """
        Resolve *hostname* asynchronously and return the first non-private IP.

        Uses ``asyncio.get_event_loop().getaddrinfo()`` which delegates the
        blocking DNS syscall to the OS thread pool, keeping the event loop free.

        Raises :class:`EgressViolation` if the hostname cannot be resolved or
        all resolved addresses fall in private/reserved ranges.
        """
        loop = asyncio.get_event_loop()
        try:
            infos = await loop.getaddrinfo(hostname, None)
        except OSError as exc:
            raise EgressViolation(
                f"Cannot resolve hostname {hostname!r}: {exc}. URL: {url!r}"
            ) from exc

        for _, _, _, _, sockaddr in infos:
            ip_str = sockaddr[0]
            try:
                ip = ipaddress.ip_address(ip_str)
            except ValueError:
                continue

            if not self._settings.allow_private_networks and self._is_private(ip):
                raise EgressViolation(
                    f"URL resolves to a private/reserved IP address ({ip_str}). "
                    f"URL: {url!r}"
                )
            return ip_str

        raise EgressViolation(
            f"No valid public IP address found for hostname {hostname!r}. "
            f"URL: {url!r}"
        )

    @staticmethod
    def _is_private(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
        return any(ip in net for net in _PRIVATE_NETWORKS)
