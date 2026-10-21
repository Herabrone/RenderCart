"""SSRF-resistant HTTP fetching with DNS validation and address pinning."""

import http.client
import ipaddress
import json
import socket
import ssl
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit, urlunsplit

from cryptography import x509


class UnsafeUrlError(ValueError):
    """The URL is malformed or resolves to a non-public destination."""


@dataclass(frozen=True)
class SafeFetchResponse:
    url: str
    status: int
    content_type: str
    body: bytes


def _resolve_public(host: str, port: int) -> str:
    try:
        literal = ipaddress.ip_address(host)
        if not literal.is_global:
            raise UnsafeUrlError("URL host must resolve to a public address")
        return str(literal)
    except ValueError as exc:
        if isinstance(exc, UnsafeUrlError):
            raise
    try:
        results = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeUrlError("URL host could not be resolved") from exc
    addresses = {ipaddress.ip_address(item[4][0]) for item in results}
    if not addresses or any(not address.is_global for address in addresses):
        raise UnsafeUrlError("URL host must resolve only to public addresses")
    return str(sorted(addresses, key=lambda address: (address.version, int(address)))[0])


def validate_public_http_url(url: str) -> tuple[str, str, int, str, str]:
    try:
        parsed = urlsplit(url)
        port = (
            parsed.port
            if parsed.port is not None
            else (443 if parsed.scheme.lower() == "https" else 80)
        )
    except ValueError as exc:
        raise UnsafeUrlError("URL is malformed") from exc
    scheme = parsed.scheme.lower()
    host = parsed.hostname
    if scheme not in {"http", "https"} or not host:
        raise UnsafeUrlError("URL must use http or https and include a hostname")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeUrlError("URL credentials are not allowed")
    if any(char in host for char in "\r\n\t\0"):
        raise UnsafeUrlError("URL hostname is malformed")
    pinned_ip = _resolve_public(host, port)
    path = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    return scheme, host, port, pinned_ip, path


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, port: int, pinned_ip: str, timeout: float) -> None:
        super().__init__(host, port, timeout=timeout)
        self.pinned_ip = pinned_ip

    def connect(self) -> None:
        self.sock = socket.create_connection((self.pinned_ip, self.port), self.timeout)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(
        self,
        host: str,
        port: int,
        pinned_ip: str,
        timeout: float,
        context: ssl.SSLContext | None = None,
    ) -> None:
        context = context or ssl.create_default_context()
        super().__init__(host, port, timeout=timeout, context=context)
        self.pinned_ip = pinned_ip
        self.context = context

    def connect(self) -> None:
        raw_socket = socket.create_connection((self.pinned_ip, self.port), self.timeout)
        self.sock = self.context.wrap_socket(raw_socket, server_hostname=self.host)


def safe_get(
    url: str,
    *,
    timeout_seconds: float = 8,
    max_bytes: int = 10 * 1024 * 1024,
    max_redirects: int = 5,
) -> SafeFetchResponse:
    """GET a public HTTP(S) URL, pinning each validated DNS result and redirect."""
    if timeout_seconds <= 0 or max_bytes <= 0 or max_redirects < 0:
        raise ValueError("timeout, response limit, and redirect limit must be positive")
    current_url = url
    for redirect in range(max_redirects + 1):
        scheme, host, port, pinned_ip, path = validate_public_http_url(current_url)
        connection_type = _PinnedHTTPSConnection if scheme == "https" else _PinnedHTTPConnection
        connection = connection_type(host, port, pinned_ip, timeout_seconds)
        host_header = f"[{host}]" if ":" in host else host
        default_port = 443 if scheme == "https" else 80
        if port != default_port:
            host_header = f"{host_header}:{port}"
        try:
            connection.request(
                "GET",
                path,
                headers={
                    "Host": host_header,
                    "User-Agent": "RenderCart-SafeFetcher/1.0",
                    "Accept-Encoding": "identity",
                    "Connection": "close",
                },
            )
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                response.close()
                if not location or redirect == max_redirects:
                    raise UnsafeUrlError("URL redirect limit exceeded")
                current_url = urljoin(current_url, location)
                continue
            content_length = response.getheader("Content-Length")
            if content_length and int(content_length) > max_bytes:
                raise UnsafeUrlError("URL response exceeds the size limit")
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise UnsafeUrlError("URL response exceeds the size limit")
            return SafeFetchResponse(
                url=current_url,
                status=response.status,
                content_type=response.getheader("Content-Type", "application/octet-stream"),
                body=body,
            )
        finally:
            connection.close()
    raise UnsafeUrlError("URL redirect limit exceeded")


def safe_post_json(
    url: str,
    payload: dict[str, object],
    *,
    allowed_hosts: set[str],
    timeout_seconds: float = 5,
    max_response_bytes: int = 2048,
) -> SafeFetchResponse:
    """POST a small JSON payload to an approved public HTTPS host without redirects."""
    scheme, host, port, pinned_ip, path = validate_public_http_url(url)
    if scheme != "https" or host.casefold() not in {item.casefold() for item in allowed_hosts}:
        raise UnsafeUrlError("Webhook host is not allowed")
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    connection = _PinnedHTTPSConnection(host, port, pinned_ip, timeout_seconds)
    host_header = f"[{host}]" if ":" in host else host
    if port != 443:
        host_header = f"{host_header}:{port}"
    try:
        connection.request(
            "POST",
            path,
            body=body,
            headers={
                "Host": host_header,
                "User-Agent": "RenderCart-Monitor/1.0",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                "Connection": "close",
            },
        )
        response = connection.getresponse()
        response_body = response.read(max_response_bytes + 1)
        if len(response_body) > max_response_bytes:
            raise UnsafeUrlError("Webhook response exceeds the size limit")
        return SafeFetchResponse(
            url=url,
            status=response.status,
            content_type=response.getheader("Content-Type", "application/octet-stream"),
            body=response_body,
        )
    finally:
        connection.close()


def tls_certificate_expiry(
    url: str,
    *,
    timeout_seconds: float = 8,
) -> datetime:
    """Read a public HTTPS server's leaf-certificate expiry using a pinned IP.

    Certificate verification is intentionally disabled for this diagnostic handshake:
    expired or self-signed certificates still need to be inspected. No HTTP request or
    user data is sent over the connection.
    """
    scheme, host, port, pinned_ip, _path = validate_public_http_url(url)
    if scheme != "https":
        raise UnsafeUrlError("TLS expiry checks require HTTPS")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    connection = _PinnedHTTPSConnection(host, port, pinned_ip, timeout_seconds, context)
    try:
        connection.connect()
        if connection.sock is None:
            raise ssl.SSLError("TLS handshake did not create a socket")
        certificate_der = connection.sock.getpeercert(binary_form=True)
        if not certificate_der:
            raise ssl.SSLError("TLS server did not provide a certificate")
        certificate = x509.load_der_x509_certificate(certificate_der)
        return certificate.not_valid_after_utc.astimezone(UTC)
    finally:
        connection.close()
