import socket

import pytest
from url_safety import validate_public_http_url


def test_rejects_private_ip_url():
    with pytest.raises(ValueError):
        validate_public_http_url("http://127.0.0.1/image.png", "image_url")


def test_rejects_localhost_url():
    with pytest.raises(ValueError):
        validate_public_http_url("https://localhost/callback", "callback_url")


def test_resolves_public_domain(monkeypatch):
    def fake_getaddrinfo(*_args, **_kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    assert validate_public_http_url("https://example.com/image.png", "image_url") == "https://example.com/image.png"
