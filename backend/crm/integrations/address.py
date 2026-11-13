import ipaddress
import re
from urllib.parse import urlsplit

from django.conf import settings

from crm.services import ApiError


def normalize_domain(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 2000:
        raise ApiError("Укажите домен или ссылку центра.")
    value = value.strip()
    if any(char.isspace() for char in value) or "\\" in value:
        raise ApiError("Некорректный адрес центра.")
    try:
        parsed = urlsplit(value if "://" in value else f"https://{value}")
        host = (
            (parsed.hostname or "").rstrip(".").encode("idna").decode("ascii").lower()
        )
        if (
            parsed.scheme != "https"
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            raise ValueError
        if (
            not re.fullmatch(
                r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", host
            )
            or len(host) > 253
        ):
            raise ValueError
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return host
        raise ValueError
    except (ValueError, UnicodeError):
        raise ApiError("Нужен публичный домен HTTPS без логина и нестандартного порта.")


def require_allowed_domain(domain):
    if not any(
        domain == allowed or domain.endswith("." + allowed)
        for allowed in settings.CENTER_ALLOWED_DOMAINS
    ):
        raise ApiError(
            "Домен центра должен быть разрешён в настройках сервера CRM.", 400
        )


def endpoint_url(domain):
    return f"https://{domain}/crm/create"
