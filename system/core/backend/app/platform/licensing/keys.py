"""Licence keys for single-device and LAN installs (see ADR-005).

A key is `MZN1.<payload>.<signature>`: base64url JSON and an Ed25519 signature over
`MZN1.<payload>`. Only the owner API holds the private key (LICENSE_SIGNING_KEY);
every install carries the public key, so keys verify without internet.
"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from app.core.config import settings

PREFIX = "MZN1"

# The production public key. Its private half lives only in the owner API's environment.
PRODUCTION_PUBLIC_KEY = "pUNlb8FG_1l3OII1VSFMVBDWv-fKl48zZCdXVxID0K8"


class LicenceError(Exception):
    pass


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _dev_private_key() -> Ed25519PrivateKey:
    """Outside production, without a configured key: a key derived from SECRET_KEY,
    so local stacks and tests can issue and verify licences."""
    seed = hashlib.sha256(f"mizan-dev-licence:{settings.SECRET_KEY}".encode()).digest()
    return Ed25519PrivateKey.from_private_bytes(seed)


def _signing_key() -> Ed25519PrivateKey:
    if settings.LICENSE_SIGNING_KEY:
        return Ed25519PrivateKey.from_private_bytes(_b64d(settings.LICENSE_SIGNING_KEY))
    if settings.is_production:
        raise LicenceError("LICENSE_SIGNING_KEY isn't configured")
    return _dev_private_key()


def _public_keys() -> list[Ed25519PublicKey]:
    keys = [Ed25519PublicKey.from_public_bytes(_b64d(settings.LICENSE_PUBLIC_KEY or PRODUCTION_PUBLIC_KEY))]
    if settings.LICENSE_SIGNING_KEY:
        keys.append(_signing_key().public_key())
    if not settings.is_production:
        keys.append(_dev_private_key().public_key())
    return keys


def can_sign() -> bool:
    try:
        _signing_key()
        return True
    except LicenceError:
        return False


# Release offers for installed servers (#89) are signed with the same key under their own prefix,
# so a release can never pass as a licence or the other way round.
RELEASE_PREFIX = "MZR1"


def sign(payload: dict, prefix: str = PREFIX) -> str:
    body = f"{prefix}.{_b64e(json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode())}"
    return f"{body}.{_b64e(_signing_key().sign(body.encode()))}"


def verify(key: str, prefix: str = PREFIX) -> dict:
    """The payload of a genuine key (expired or not); LicenceError otherwise."""
    parts = (key or "").strip().split(".")
    if len(parts) != 3 or parts[0] != prefix:
        raise LicenceError("Not a Mizan licence key")
    body, signature = f"{parts[0]}.{parts[1]}", parts[2]
    try:
        raw_sig = _b64d(signature)
    except ValueError:
        raise LicenceError("Not a Mizan licence key") from None
    for public in _public_keys():
        try:
            public.verify(raw_sig, body.encode())
            break
        except InvalidSignature:
            continue
    else:
        raise LicenceError("This licence key wasn't issued by Mizan")
    try:
        return json.loads(_b64d(parts[1]))
    except ValueError:
        raise LicenceError("Not a Mizan licence key") from None


def is_current(payload: dict, now: datetime | None = None) -> bool:
    until = payload.get("valid_until")
    if not until:
        return False
    moment = datetime.fromisoformat(until)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return (now or datetime.now(UTC)) <= moment
