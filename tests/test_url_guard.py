"""Unit tests for URL Guard and SSRF Protection."""

import pytest
from backend.security.url_guard import validate_media_url, SecurityValidationError


def test_valid_http_and_https_urls():
    assert validate_media_url("https://example.com/watch?v=test") == "https://example.com/watch?v=test"
    assert validate_media_url("http://cdn.example.org/audio.mp3") == "http://cdn.example.org/audio.mp3"
    assert validate_media_url("  https://vimeo.com/12345  ") == "https://vimeo.com/12345"


def test_reject_empty_or_whitespace():
    with pytest.raises(SecurityValidationError, match="cannot be empty"):
        validate_media_url("")
    with pytest.raises(SecurityValidationError, match="cannot be empty"):
        validate_media_url("   ")


def test_reject_unauthorized_schemes():
    unauthorized = [
        "file:///C:/Windows/System32/calc.exe",
        "ftp://files.example.com/media.mp4",
        "gopher://evil.com/1",
        "javascript:alert(1)",
        "data:text/html;base64,PHNjcmlwdD4=",
    ]
    for url in unauthorized:
        with pytest.raises(SecurityValidationError, match="protocol"):
            validate_media_url(url)


def test_reject_loopback_and_local():
    loopbacks = [
        "http://localhost:8080/api",
        "http://localhost/video",
        "http://127.0.0.1:8899/admin",
        "http://127.0.0.2/test",
        "http://[::1]/video",
    ]
    for url in loopbacks:
        with pytest.raises(SecurityValidationError):
            validate_media_url(url)


def test_reject_cloud_metadata():
    metadata_endpoints = [
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://instance-data/latest/meta-data/",
    ]
    for url in metadata_endpoints:
        with pytest.raises(SecurityValidationError):
            validate_media_url(url)


def test_reject_private_rfc1918_networks():
    private_ips = [
        "http://10.0.0.1/stream",
        "http://172.16.0.5/stream",
        "http://192.168.1.1/router",
        "http://192.168.0.100/media.mp4",
    ]
    for url in private_ips:
        with pytest.raises(SecurityValidationError, match="restricted"):
            validate_media_url(url)


def test_reject_command_injection_and_control_chars():
    malicious = [
        "https://example.com/video\ncurl evil.com",
        "https://example.com/video\r\nevil",
        "https://example.com/video`whoami`",
        "https://example.com/video\0malicious",
    ]
    for url in malicious:
        with pytest.raises(SecurityValidationError, match="control characters"):
            validate_media_url(url)
