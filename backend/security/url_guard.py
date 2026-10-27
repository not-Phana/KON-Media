"""URL validation and SSRF protection guard for KON Media.

Guarantees that user-submitted media URLs:
1. Use only allowed protocols (http, https).
2. Do not target loopback interfaces (localhost, 127.0.0.1, ::1).
3. Do not probe private RFC1918 intranets (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16).
4. Do not access cloud metadata services (169.254.169.254, metadata.google.internal).
5. Are well-formed and free of dangerous shell control characters.
"""

import ipaddress
import socket
from urllib.parse import urlsplit


class SecurityValidationError(ValueError):
    """Raised when a URL violates security policies."""
    pass


_ALLOWED_SCHEMES = ("http", "https")

_BLOCKED_HOSTNAMES = (
    "localhost",
    "metadata.google.internal",
    "instance-data",
)

_BLOCKED_NETWORKS = (
    ipaddress.ip_network("127.0.0.0/8"),      # Loopback IPv4
    ipaddress.ip_network("10.0.0.0/8"),       # Private IPv4
    ipaddress.ip_network("172.16.0.0/12"),    # Private IPv4
    ipaddress.ip_network("192.168.0.0/16"),   # Private IPv4
    ipaddress.ip_network("169.254.0.0/16"),   # Link-local / Cloud metadata
    ipaddress.ip_network("0.0.0.0/8"),        # Current network
    ipaddress.ip_network("224.0.0.0/4"),      # Multicast IPv4
    ipaddress.ip_network("240.0.0.0/4"),      # Reserved
    ipaddress.ip_network("::1/128"),          # Loopback IPv6
    ipaddress.ip_network("fc00::/7"),         # Unique local address (IPv6 private)
    ipaddress.ip_network("fe80::/10"),        # Link-local IPv6
)


def validate_media_url(url: str) -> str:
    """Validate a user-provided URL against security rules.

    Returns the cleaned, validated URL string or raises SecurityValidationError.
    """
    if not url or not isinstance(url, str) or not url.strip():
        raise SecurityValidationError("URL cannot be empty.")

    cleaned_url = url.strip()

    # Reject URLs containing newline, carriage return, null bytes or backticks
    if any(c in cleaned_url for c in ("\r", "\n", "\0", "`")):
        raise SecurityValidationError("URL contains invalid control characters.")

    try:
        parsed = urlsplit(cleaned_url)
    except Exception as e:
        raise SecurityValidationError(f"Invalid URL structure: {e}")

    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise SecurityValidationError(
            f"Invalid URL protocol '{scheme}'. Only HTTP and HTTPS are permitted."
        )

    hostname = (parsed.hostname or "").lower().rstrip(".")
    if not hostname:
        raise SecurityValidationError("URL must include a valid hostname.")

    # Check blocked hostnames
    for blocked in _BLOCKED_HOSTNAMES:
        if hostname == blocked or hostname.endswith("." + blocked):
            raise SecurityValidationError(f"Access to '{hostname}' is blocked for security.")

    # Check literal IP address or resolve hostname to IP
    try:
        # Check if hostname is an IP literal directly
        ip = ipaddress.ip_address(hostname)
        _check_ip_allowed(ip)
    except ValueError:
        # Hostname is a domain name. Resolve addresses to ensure it does not map to private/loopback
        try:
            addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            for _, _, _, _, sockaddr in addr_info:
                ip_str = sockaddr[0]
                ip = ipaddress.ip_address(ip_str)
                _check_ip_allowed(ip)
        except socket.gaierror as e:
            # If domain cannot be resolved, let yt-dlp handle external resolution or report error
            pass

    return cleaned_url


def _check_ip_allowed(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    """Ensure the given IP address does not fall within any blocked ranges."""
    # Convert IPv4-mapped IPv6 address to IPv4
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped

    for network in _BLOCKED_NETWORKS:
        if ip in network:
            raise SecurityValidationError(
                f"Destination IP address {ip} is in a restricted local or private range."
            )
