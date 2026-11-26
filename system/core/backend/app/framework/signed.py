"""Short-lived signed links (#43, #44): an HMAC-SHA256 token over a small JSON payload with an expiry,
for URLs that can't carry the session (an <img src>, a download link).

The key is derived from SECRET_KEY and the token's purpose, so a token made for one purpose is
refused for another, and it never passes for a session JWT (a different format and key).
The token only proves that the server issued this link recently: the route serving it still
checks that the user it names may read the resource now.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time


class InvalidToken(ValueError):
    pass


class ExpiredToken(InvalidToken):
    pass


def _key(purpose: str) -> bytes:
    from app.core.config import settings

    return hmac.new(settings.SECRET_KEY.encode(), f"mizan-signed:{purpose}".encode(), hashlib.sha256).digest()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sign(purpose: str, data: dict, ttl_seconds: int, *, now: float | None = None) -> str:
    payload = _b64(json.dumps({**data, "exp": int((now or time.time()) + ttl_seconds)}, separators=(",", ":")).encode())
    mac = _b64(hmac.new(_key(purpose), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{mac}"


def verify(purpose: str, token: str, *, now: float | None = None) -> dict:
    """The payload, or InvalidToken (tampered, other purpose) / ExpiredToken."""
    try:
        payload, mac = token.split(".")
        expected = _b64(hmac.new(_key(purpose), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(mac, expected):
            raise InvalidToken("bad signature")
        data = json.loads(_unb64(payload))
    except InvalidToken:
        raise
    except (ValueError, TypeError) as e:
        raise InvalidToken("malformed") from e
    if not isinstance(data, dict) or not isinstance(data.get("exp"), int):
        raise InvalidToken("malformed")
    if data["exp"] < (now or time.time()):
        raise ExpiredToken("expired")
    return data
