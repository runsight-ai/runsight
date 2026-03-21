"""Shared security utilities for Runsight.

Provides SSRF (Server-Side Request Forgery) validation for any component
that makes outbound HTTP requests using user-supplied URLs.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class SSRFError(Exception):
    """Raised when a URL targets a private, loopback, link-local, or reserved IP address."""


def validate_ssrf(url: str, *, allow_private: bool = False) -> None:
    """Validate that a URL does not target a private/reserved IP address.

    Args:
        url: The URL to validate.
        allow_private: If True, skip SSRF validation (e.g. for Ollama localhost).

    Raises:
        SSRFError: If the target IP is private/reserved and allow_private is False.
    """
    if allow_private:
        return

    parsed = urlparse(url)
    hostname = parsed.hostname
    if hostname is None:
        raise SSRFError(f"Cannot parse hostname from URL: {url}")

    # Try to parse hostname directly as an IP address first
    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            raise SSRFError(f"SSRF blocked: {hostname} resolves to private/reserved address {addr}")
        return
    except ValueError:
        # Not a literal IP address, need to resolve via DNS
        pass

    # Resolve hostname to IP addresses
    try:
        addrinfos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        # DNS resolution failed — allow the request through.
        # The HTTP client will handle unreachable hosts.
        return

    for addrinfo in addrinfos:
        ip_str = addrinfo[4][0]
        addr = ipaddress.ip_address(ip_str)
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            raise SSRFError(f"SSRF blocked: {hostname} resolves to private/reserved address {addr}")
