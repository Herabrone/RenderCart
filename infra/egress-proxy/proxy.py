"""HTTPS CONNECT proxy that permits only public DNS-pinned destinations on port 443."""

import ipaddress
import select
import socket
import socketserver
import threading
import time
from urllib.parse import urlsplit

_MAX_HEADER_BYTES = 16_384
_CONNECT_TIMEOUT_SECONDS = 8
_MAX_TUNNEL_SECONDS = 600
_MAX_TUNNEL_BYTES = 25_000_000
_MAX_CLIENT_BYTES_PER_HOUR = 120_000_000
_TUNNEL_CAPACITY = threading.BoundedSemaphore(12)
_CLIENT_USAGE: dict[str, tuple[int, int]] = {}
_USAGE_LOCK = threading.Lock()


def _destination(authority: str) -> tuple[str, int, str]:
    parsed = urlsplit(f"//{authority}")
    host = parsed.hostname
    port = parsed.port
    if (
        not host
        or port != 443
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("CONNECT target rejected")
    ascii_host = host.encode("idna").decode("ascii")
    try:
        literal = ipaddress.ip_address(ascii_host)
        addresses = {literal}
    except ValueError:
        answers = socket.getaddrinfo(ascii_host, port, type=socket.SOCK_STREAM)
        addresses = {ipaddress.ip_address(answer[4][0]) for answer in answers}
    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("CONNECT target rejected")
    pinned_ip = str(sorted(addresses, key=lambda address: (address.version, int(address)))[0])
    return ascii_host, port, pinned_ip


class _ProxyHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        acquired = False
        upstream: socket.socket | None = None
        self.request.settimeout(_CONNECT_TIMEOUT_SECONDS)
        reader = self.request.makefile("rb")
        try:
            line = reader.readline(8193)
            if len(line) > 8192:
                self._reply(431, "Request Header Fields Too Large")
                return
            parts = line.decode("ascii", "strict").strip().split()
            if len(parts) != 3 or parts[0] != "CONNECT" or parts[2] != "HTTP/1.1":
                self._reply(405, "CONNECT Required")
                return
            header_bytes = len(line)
            while True:
                header = reader.readline(8193)
                header_bytes += len(header)
                if header_bytes > _MAX_HEADER_BYTES:
                    self._reply(431, "Request Header Fields Too Large")
                    return
                if header in {b"\r\n", b"\n", b""}:
                    break
            acquired = _TUNNEL_CAPACITY.acquire(blocking=False)
            if not acquired:
                self._reply(429, "Proxy Capacity Reached")
                return
            try:
                _host, port, pinned_ip = _destination(parts[1])
                upstream = socket.create_connection((pinned_ip, port), _CONNECT_TIMEOUT_SECONDS)
            except (OSError, ValueError, UnicodeError):
                _TUNNEL_CAPACITY.release()
                acquired = False
                self._reply(403, "Destination Not Allowed")
                return
            self.request.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        except (OSError, UnicodeError):
            if upstream is not None:
                upstream.close()
            if acquired:
                _TUNNEL_CAPACITY.release()
            return
        finally:
            reader.close()
        try:
            assert upstream is not None
            self._relay(upstream)
        finally:
            upstream.close()
            _TUNNEL_CAPACITY.release()

    def _reply(self, status: int, reason: str) -> None:
        try:
            response = (
                f"HTTP/1.1 {status} {reason}\r\n"
                "Connection: close\r\nContent-Length: 0\r\n\r\n"
            )
            self.request.sendall(
                response.encode()
            )
        except OSError:
            pass

    def _relay(self, upstream: socket.socket) -> None:
        end = time.monotonic() + _MAX_TUNNEL_SECONDS
        transferred = 0
        client_ip = str(self.client_address[0])
        peers = [self.request, upstream]
        while time.monotonic() < end:
            try:
                readable, _, _ = select.select(peers, [], [], 5)
                for source in readable:
                    payload = source.recv(65_536)
                    if not payload:
                        return
                    transferred += len(payload)
                    if (
                        transferred > _MAX_TUNNEL_BYTES
                        or not _allow_client_bytes(client_ip, len(payload))
                    ):
                        return
                    destination = upstream if source is self.request else self.request
                    destination.sendall(payload)
            except (OSError, ValueError):
                return


def _allow_client_bytes(client_ip: str, count: int) -> bool:
    current_hour = int(time.time() // 3600)
    with _USAGE_LOCK:
        hour, total = _CLIENT_USAGE.get(client_ip, (current_hour, 0))
        if hour != current_hour:
            total = 0
        total += count
        _CLIENT_USAGE[client_ip] = (current_hour, total)
        return total <= _MAX_CLIENT_BYTES_PER_HOUR


class _ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with _ThreadedServer(("0.0.0.0", 3128), _ProxyHandler) as server:
        server.serve_forever(poll_interval=0.5)
