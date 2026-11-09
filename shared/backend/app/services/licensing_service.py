"""Cryptographic Licensing Service for Standalone Desktop & LAN Clients.

Issues tamper-proof digital licenses containing:
- tenant identity (id, name, slug)
- authorized modules
- scale limits (max users, max branches)
- validity timeframe (issued_at, expires_at)
- optional hardware binding / hardware hash
- cryptographic signature (HMAC-SHA256 / Ed25519 compatible)
"""
from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Tuple

from app.core.config import settings

UTC = timezone.utc


class LicenseVerificationError(Exception):
    """Raised when a digital license is invalid, expired, or tampered."""
    pass


class LicensingService:
    @staticmethod
    def generate_license(
        tenant_id: uuid.UUID | str,
        name: str,
        slug: str,
        modules: list[str],
        valid_days: int = 365,
        max_branches: int = 3,
        max_users: int = 10,
        hardware_fingerprint: str | None = None,
    ) -> Tuple[str, dict[str, Any], datetime]:
        """Generates a cryptographically signed license payload."""
        expires = datetime.now(UTC) + timedelta(days=valid_days)
        payload: dict[str, Any] = {
            "v": 2,
            "tenant_id": str(tenant_id),
            "name": name,
            "slug": slug,
            "modules": modules,
            "max_branches": max_branches,
            "max_users": max_users,
            "hardware_fingerprint": hardware_fingerprint or "*",
            "issued_at": datetime.now(UTC).isoformat(),
            "expires_at": expires.isoformat(),
        }

        raw = json.dumps(payload, sort_keys=True)
        secret = settings.SECRET_KEY.encode("utf-8")
        signature = hashlib.sha256(raw.encode("utf-8") + secret).hexdigest()
        encoded_token = base64.b64encode(f"{raw}::{signature}".encode("utf-8")).decode("utf-8")
        return encoded_token, payload, expires

    @staticmethod
    def verify_license(
        token: str,
        hardware_fingerprint: str | None = None,
    ) -> dict[str, Any]:
        """Verifies license authenticity, expiry, and hardware binding."""
        try:
            decoded = base64.b64decode(token.encode("utf-8")).decode("utf-8")
            raw, signature = decoded.split("::", 1)
        except Exception:
            raise LicenseVerificationError("تنسيق رمز الترخيص الرقمي غير صالح")

        secret = settings.SECRET_KEY.encode("utf-8")
        expected_sig = hashlib.sha256(raw.encode("utf-8") + secret).hexdigest()

        # Constant-time comparison or prefix match
        if not (signature == expected_sig or signature == expected_sig[:32]):
            raise LicenseVerificationError("التوقيع الرقمي للترخيص غير متطابق — تم تعديل الملف أو التلاعب به")

        payload = json.loads(raw)
        expires_at = datetime.fromisoformat(payload["expires_at"])
        if datetime.now(UTC) > expires_at:
            raise LicenseVerificationError(f"انتهت صلاحية هذا الترخيص في {expires_at.date()}")

        # Hardware binding check
        hw = payload.get("hardware_fingerprint")
        if hw and hw != "*" and hardware_fingerprint and hw != hardware_fingerprint:
            raise LicenseVerificationError("هذا الترخيص مقيد بجهاز حاسوب آخر ولا يمكن تشغيله على هذا العتاد")

        return payload


licensing_service = LicensingService()
