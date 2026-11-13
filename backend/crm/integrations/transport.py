"""HTTPS-адаптер: фиксируем проверенный IP, сохраняя TLS/SNI исходного домена."""

import http.client
import ipaddress
import json
import socket
import ssl
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Protocol

from django.utils import timezone

from .address import require_allowed_domain


@dataclass(frozen=True)
class Reply:
    status: int
    data: dict
    retry_after: int = 0


class Transport(Protocol):
    def request(
        self,
        domain: str,
        key: str,
        path: str,
        payload: dict | None = None,
        operation_id: str = "",
    ) -> Reply: ...


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, domain, address):
        super().__init__(domain, timeout=15, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        connection = socket.create_connection((self.address, 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(connection, server_hostname=self.host)
        except Exception:
            connection.close()
            raise


def public_address(domain):
    records = socket.getaddrinfo(domain, 443, type=socket.SOCK_STREAM)
    addresses = list(dict.fromkeys(record[4][0] for record in records))
    if not addresses or any(
        not ipaddress.ip_address(address).is_global for address in addresses
    ):
        raise ValueError("unsafe_address")
    return addresses[0]


def retry_delay(value):
    try:
        seconds = int(value)
    except (ValueError, TypeError):
        try:
            seconds = int(
                (parsedate_to_datetime(value) - timezone.now()).total_seconds()
            )
        except (ValueError, TypeError, OverflowError):
            return 0
    return max(0, min(seconds, 86400))


class HTTPSClient:
    def request(self, domain, key, path, payload=None, operation_id=""):
        require_allowed_domain(domain)
        connection = PinnedHTTPS(domain, public_address(domain))
        headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
        body = None
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode()
            headers.update(
                {"Content-Type": "application/json", "Idempotency-Key": operation_id}
            )
        try:
            connection.request(
                "POST" if payload is not None else "GET",
                path,
                body=body,
                headers=headers,
            )
            response = connection.getresponse()
            raw = response.read(65537)
            if len(raw) > 65536:
                return Reply(response.status, {})
            try:
                data = json.loads(raw)
            except (ValueError, UnicodeError):
                data = {}
            return Reply(
                response.status,
                data if isinstance(data, dict) else {},
                retry_delay(response.getheader("Retry-After")),
            )
        finally:
            connection.close()
