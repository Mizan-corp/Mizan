"""GET /clinic/media/{token}: a clinical file behind a short-lived signed link (media.py).

Mounted outside the clinic router's session guards (an <img src> carries no Authorization
header); the token stands in for the session, and every request re-checks the user, the module
and the user's access to the patient's record, and is logged.
"""
from __future__ import annotations

import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.healthcare.modules.healthcare_clinic import media
from app.activities.healthcare.modules.healthcare_clinic import service as access
from app.activities.healthcare.modules.healthcare_clinic.models import ClinicConsentForm
from app.db.base import get_db
from app.framework import files, signed
from app.platform.auth.models.user import User

router = APIRouter(prefix="/clinic", tags=["Healthcare & Clinic ERP"])

GONE = "انتهت صلاحية رابط الملف؛ افتحه من جديد من ملف المريض"


async def _signature(db: AsyncSession, record_id: str) -> tuple[str, str, str, str, str]:
    c = await db.get(ClinicConsentForm, record_id)
    if not c:
        raise HTTPException(404, "الملف غير موجود")
    return c.patient_id, c.signature_path, "image/png", f"signature-{c.consent_ref}.png", "signature"


# kind → loader(db, id) → (patient_id, storage key, content type, file name, log resource)
KINDS = {"signature": _signature}


def register(kind: str, loader) -> None:
    KINDS[kind] = loader


@router.get("/media/{token}")
async def serve_media(token: str, db: AsyncSession = Depends(get_db)):
    try:
        data = signed.verify(media.PURPOSE, token)
    except signed.ExpiredToken:
        raise HTTPException(410, GONE)
    except signed.InvalidToken:
        raise HTTPException(403, "رابط الملف غير صالح")
    loader = KINDS.get(data.get("k"))
    if loader is None:
        raise HTTPException(403, "رابط الملف غير صالح")

    from app.framework.activation import get_active_modules
    from app.platform.permissions.access import load_acting
    from app.platform.tenancy.context import bind_tenant

    try:
        tenant_id, user_id = uuid.UUID(data["t"]), uuid.UUID(data["u"])
    except (KeyError, ValueError):
        raise HTTPException(403, "رابط الملف غير صالح")
    await bind_tenant(db, tenant_id)
    user = (await db.execute(select(User).where(User.id == user_id, User.tenant_id == tenant_id,
                                                User.is_active))).scalar_one_or_none()
    if not user:
        raise HTTPException(403, "رابط الملف غير صالح")
    if "healthcare_clinic" not in await get_active_modules(db):
        raise HTTPException(403, "وحدة العيادات غير مفعلة")
    await load_acting(db, user)
    patient_id, key, content_type, filename, resource = await loader(db, str(data.get("id")))
    how = await access.require_clinical_access(db, user, patient_id)
    body = await files.read_private(key)
    await access.log_access(db, user, resource, how, patient_id, 1)
    inline = content_type.startswith("image/")
    return Response(body, media_type=content_type, headers={
        "Content-Disposition": f"{'inline' if inline else 'attachment'}; filename*=UTF-8''{quote(filename)}",
        "Cache-Control": "private, max-age=60",
        "Content-Security-Policy": "default-src 'none'; sandbox",
        "Referrer-Policy": "no-referrer",
    })
