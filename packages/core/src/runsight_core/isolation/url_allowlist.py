"""Hostname normalization for host-owned HTTP URL allowlists."""

from __future__ import annotations

from ipaddress import ip_address
from urllib.parse import urlparse


def normalize_allowlist_hostname(value: object) -> str:
    """Return a lowercase hostname for allowlist entries, or empty string if invalid."""
    entry = str(value).strip()
    if not entry:
        return ""

    try:
        parsed = urlparse(entry)
        if parsed.hostname is not None:
            if parsed.netloc and ":" in parsed.netloc:
                parsed.port
            return parsed.hostname.strip().lower()
    except ValueError:
        return ""
    if "://" in entry:
        return ""

    host_part = entry.split("/", 1)[0].strip()
    if not host_part or "@" in host_part:
        return ""

    if host_part.startswith("["):
        closing_bracket = host_part.find("]")
        if closing_bracket == -1:
            return ""
        hostname = host_part[1:closing_bracket].strip()
        port_suffix = host_part[closing_bracket + 1 :]
        if not hostname or (
            port_suffix and not (port_suffix.startswith(":") and port_suffix[1:].isdigit())
        ):
            return ""
        return hostname.lower()

    if host_part.count(":") > 1:
        try:
            return str(ip_address(host_part)).lower()
        except ValueError:
            return ""

    raw_hostname, separator, raw_port = host_part.rpartition(":")
    if separator:
        hostname = raw_hostname if raw_hostname and raw_port.isdigit() else ""
    else:
        hostname = host_part
    return hostname.strip().lower()
