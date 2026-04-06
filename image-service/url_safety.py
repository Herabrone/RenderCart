import ipaddress
import socket
from urllib.parse import urlparse


ALLOWED_URL_SCHEMES = {"http", "https"}


def _is_public_ip(ip_address: ipaddress._BaseAddress) -> bool:
    return not (
        ip_address.is_private
        or ip_address.is_loopback
        or ip_address.is_link_local
        or ip_address.is_multicast
        or ip_address.is_reserved
        or ip_address.is_unspecified
    )


def validate_public_http_url(url: str, field_name: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_URL_SCHEMES:
        raise ValueError(f"{field_name} must use http or https")
    if not parsed.hostname:
        raise ValueError(f"{field_name} must include a hostname")
    if parsed.username or parsed.password:
        raise ValueError(f"{field_name} must not include credentials")

    hostname = parsed.hostname
    if hostname.lower() == "localhost":
        raise ValueError(f"{field_name} must resolve to a public address")

    try:
        ip_address = ipaddress.ip_address(hostname)
        if not _is_public_ip(ip_address):
            raise ValueError(f"{field_name} must resolve to a public address")
        return url
    except ValueError:
        pass

    try:
        addresses = socket.getaddrinfo(hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"{field_name} could not be resolved") from exc

    if not addresses:
        raise ValueError(f"{field_name} could not be resolved")

    for _, _, _, _, sockaddr in addresses:
        ip_address = ipaddress.ip_address(sockaddr[0])
        if not _is_public_ip(ip_address):
            raise ValueError(f"{field_name} must resolve to a public address")

    return url
