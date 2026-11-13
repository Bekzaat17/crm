import hashlib
import secrets


def digest(token):
    """Одностороннее хеширование одноразовых токенов перед сохранением."""
    return hashlib.sha256(token.encode()).hexdigest()


def new_token():
    return secrets.token_urlsafe(32)
