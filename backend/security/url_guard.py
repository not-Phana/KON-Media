"""URL validation and SSRF protection guard for KON Media.

Guarantees that user-submitted media URLs:
1. Use only allowed protocols (http, https).
2. Do not target loopback interfaces (localhost, 127.0.0.1, ::1).
3. Do not probe private RFC1918 intranets (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16).
4. Do not access cloud metadata services (169.254.169.254, metadata.google.internal).
5. Are well-formed and free of dangerous shell control characters.
"""

import contextlib
import ipaddress
import socket
import threading
from urllib.parse import urlsplit
from typing import Any, Dict, Optional


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


def is_ip_allowed(ip: ipaddress.IPv4Address | ipaddress.IPv6Address | str) -> bool:
    """Check whether an IP address is public and allowed, or in a restricted network."""
    try:
        if isinstance(ip, str):
            ip = ipaddress.ip_address(ip)
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        for network in _BLOCKED_NETWORKS:
            if ip in network:
                return False
        return True
    except Exception:
        return False


def _check_ip_allowed(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    """Ensure the given IP address does not fall within any blocked ranges."""
    if not is_ip_allowed(ip):
        raise SecurityValidationError(
            f"Destination IP address {ip} is in a restricted local or private range."
        )


# =====================================================================
# Connect-Time Socket Guard for SSRF & DNS Rebinding Protection
# =====================================================================

_real_getaddrinfo = socket.getaddrinfo
_thread_guard = threading.local()


def _guarded_getaddrinfo(host, *args, **kwargs):
    results = _real_getaddrinfo(host, *args, **kwargs)
    if not getattr(_thread_guard, "active", False):
        return results

    allowed = [r for r in results if is_ip_allowed(r[4][0])]
    if not allowed:
        raise socket.gaierror(f"Refusing to connect to non-global address for host {host!r}")
    return allowed


socket.getaddrinfo = _guarded_getaddrinfo


@contextlib.contextmanager
def socket_guard_scope():
    """Apply the connect-time address guard for the calling thread while the block runs."""
    _thread_guard.active = True
    try:
        yield
    finally:
        _thread_guard.active = False


def is_spotify_hostname(hostname: Optional[str]) -> bool:
    """Strictly verify if a hostname belongs to legitimate Spotify domains.

    Prevents deceptive hostnames like 'spotify.com.attacker.com',
    'not-spotify.com', 'fake-spotify.com', or 'spotify.evil.org'.
    """
    if not hostname:
        return False
    h = hostname.lower().rstrip(".")
    if h in ("spotify.com", "spotify.link"):
        return True
    if h.endswith(".spotify.com") or h.endswith(".spotify.link"):
        return True
    return False


def detect_spotify_source(url: str) -> Optional[Dict[str, Any]]:
    """Detect and classify Spotify URLs with content identification and canonicalization.

    Returns None if the URL does not belong to a valid Spotify domain.
    Returns a structured classification dictionary if valid.
    """
    if not url or not isinstance(url, str):
        return None

    cleaned_url = url.strip()
    try:
        parsed = urlsplit(cleaned_url)
    except Exception:
        return None

    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        return None

    hostname = (parsed.hostname or "").lower().rstrip(".")
    if not is_spotify_hostname(hostname):
        return None

    # Parse path components
    path = parsed.path.strip("/")
    parts = [p for p in path.split("/") if p]

    # Handle localized paths (e.g. /intl-en/track/..., /intl-de/album/...)
    if parts and parts[0].startswith("intl-"):
        parts = parts[1:]

    content_type = "content"
    content_id = None
    title = "Spotify Content"

    if parts:
        first = parts[0].lower()
        if first in ("track", "album", "playlist", "artist", "episode", "show"):
            content_type = first
            content_id = parts[1] if len(parts) > 1 else None
            title = f"Spotify {first.capitalize()}"
        elif first == "user" and len(parts) >= 4 and parts[2].lower() == "playlist":
            content_type = "playlist"
            content_id = parts[3]
            title = "Spotify Playlist"
        elif first == "user":
            content_type = "user"
            content_id = parts[1] if len(parts) > 1 else None
            title = "Spotify User Profile"
        elif hostname.endswith("spotify.link"):
            content_type = "shared_link"
            content_id = parts[0]
            title = "Spotify Shared Link"
        else:
            content_type = first
            content_id = parts[1] if len(parts) > 1 else None
            title = f"Spotify {first.capitalize()}"
    elif hostname.endswith("spotify.link"):
        content_type = "shared_link"
        title = "Spotify Shared Link"

    # Construct canonical web URL
    if content_id and content_type in ("track", "album", "playlist", "artist", "episode", "show"):
        canonical_url = f"https://open.spotify.com/{content_type}/{content_id}"
    else:
        canonical_url = cleaned_url

    return {
        "is_spotify": True,
        "source": "spotify",
        "hostname": hostname,
        "content_type": content_type,
        "content_id": content_id,
        "title": title,
        "web_url": cleaned_url,
        "canonical_url": canonical_url,
    }


_REDIRECT_GUARD_INSTALLED = False


def install_network_security_guards() -> None:
    """Install runtime guards into urllib and yt-dlp to validate HTTP redirects against SSRF and private networks.

    Guarantees that an initial URL cannot redirect to loopback interfaces, cloud metadata,
    or internal RFC1918 private subnets.
    """
    global _REDIRECT_GUARD_INSTALLED
    if _REDIRECT_GUARD_INSTALLED:
        return

    import urllib.request

    # 1. Standard library urllib redirect guard
    orig_urllib_redirect = urllib.request.HTTPRedirectHandler.redirect_request

    def secure_urllib_redirect(self, req, fp, code, msg, headers, newurl):
        validate_media_url(newurl)
        return orig_urllib_redirect(self, req, fp, code, msg, headers, newurl)

    urllib.request.HTTPRedirectHandler.redirect_request = secure_urllib_redirect

    # 2. yt-dlp internal urllib redirect guard
    try:
        import yt_dlp.networking._urllib as ytdlp_urllib
        if hasattr(ytdlp_urllib, "RedirectHandler"):
            orig_ytdlp_redirect = ytdlp_urllib.RedirectHandler.redirect_request

            def secure_ytdlp_redirect(self, req, fp, code, msg, headers, newurl):
                validate_media_url(newurl)
                return orig_ytdlp_redirect(self, req, fp, code, msg, headers, newurl)

            ytdlp_urllib.RedirectHandler.redirect_request = secure_ytdlp_redirect
    except Exception:
        pass

    _REDIRECT_GUARD_INSTALLED = True


# Automatically activate redirect protections upon module load
install_network_security_guards()
