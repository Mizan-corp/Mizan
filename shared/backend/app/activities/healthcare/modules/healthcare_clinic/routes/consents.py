"""Consent forms with a drawn signature (#43). Reading, signing, revoking and the PDF are clinical:
a doctor or nurse who reaches the patient's record (service.require_clinical_access), logged.
The signature PNG goes to the private file store (framework.files.store_private), never the row."""
from __future__ import annotations

import base64
import binascii
import html
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.healthcare.modules.healthcare_clinic import media
from app.activities.healthcare.modules.healthcare_clinic import service as access
from app.activities.healthcare.modules.healthcare_clinic.models import ClinicConsentForm, ClinicEncounter
from app.activities.healthcare.modules.healthcare_clinic.routes.charts import patient_or_404
from app.db.base import get_db
from app.dependencies import get_current_user
from app.framework import files
from app.platform.audit.service import log as audit_log
from app.platform.auth.models.user import User

router = APIRouter()

MAX_SIGNATURE_BYTES = 1024 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
KINDS_AR = {"procedure": "إجراء طبي", "surgery": "عملية جراحية", "data_sharing": "مشاركة البيانات الطبية", "other": "أخرى"}
RELATIONS_AR = {"self": "المريض نفسه", "guardian": "الوصي القانوني", "parent": "ولي الأمر", "spouse": "الزوج / الزوجة", "other": "أخرى"}
FONTS = Path(__file__).resolve().parents[5] / "platform" / "printing" / "fonts"
CAIRO = ZoneInfo("Africa/Cairo")


class ConsentCreate(BaseModel):
    kind: Literal["procedure", "surgery", "data_sharing", "other"] = "procedure"
    title: str = Field(..., min_length=3, max_length=200)
    body: str = Field(..., min_length=10, max_length=20000)
    signer_name: str = Field(..., min_length=3, max_length=128)
    signer_relation: Literal["self", "guardian", "parent", "spouse", "other"] = "self"
    signature_png: str = Field(..., description="data:image/png;base64,… from the signature pad")
    encounter_id: str | None = None


class ConsentRevoke(BaseModel):
    reason: str = Field(..., min_length=3, max_length=1000)


def _require_clinician(user: User) -> None:
    if not access.is_clinician(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="نماذج الموافقة للأطباء وطاقم التمريض")


def _signature_bytes(data_url: str) -> bytes:
    prefix = "data:image/png;base64,"
    if not data_url.startswith(prefix):
        raise HTTPException(status_code=400, detail="التوقيع يجب أن يكون صورة PNG من لوحة التوقيع")
    try:
        raw = base64.b64decode(data_url[len(prefix):], validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="صورة التوقيع تالفة")
    if not raw.startswith(PNG_MAGIC):
        raise HTTPException(status_code=400, detail="صورة التوقيع ليست PNG")
    if len(raw) > MAX_SIGNATURE_BYTES:
        raise HTTPException(status_code=413, detail="صورة التوقيع أكبر من 1 ميجابايت")
    return raw


def _out(c: ClinicConsentForm) -> dict:
    out = {k: getattr(c, k) for k in (
        "id", "consent_ref", "patient_id", "encounter_id", "kind", "title", "body", "signer_name", "signer_relation",
        "signed_at", "witness_name", "revoked_at", "revoke_reason", "created_at")}
    out["status"] = "revoked" if c.revoked_at else "active"
    return out


async def _consent(db: AsyncSession, user: User, consent_id: str) -> tuple[ClinicConsentForm, str]:
    c = (await db.execute(select(ClinicConsentForm).where(
        ClinicConsentForm.id == consent_id, ClinicConsentForm.tenant_id == user.tenant_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="نموذج الموافقة غير موجود")
    return c, await access.require_clinical_access(db, user, c.patient_id)


@router.get("/patients/{patient_id}/consents")
async def list_consents(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    patient = await patient_or_404(db, current_user.tenant_id, patient_id)
    how = await access.require_clinical_access(db, current_user, patient.id)
    rows = (await db.execute(select(ClinicConsentForm).where(
        ClinicConsentForm.tenant_id == current_user.tenant_id, ClinicConsentForm.patient_id == patient.id,
    ).order_by(ClinicConsentForm.signed_at.desc()))).scalars().all()
    await access.log_access(db, current_user, "consents", how, patient.id, len(rows))
    return [_out(c) for c in rows]


@router.post("/patients/{patient_id}/consents")
async def create_consent(
    patient_id: str,
    payload: ConsentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sign a consent: the signer draws on the pad, the clinician signing it in is the witness."""
    _require_clinician(current_user)
    patient = await patient_or_404(db, current_user.tenant_id, patient_id)
    await access.require_clinical_access(db, current_user, patient.id)
    signature = _signature_bytes(payload.signature_png)
    if payload.encounter_id and not await db.scalar(select(ClinicEncounter.id).where(
            ClinicEncounter.id == payload.encounter_id, ClinicEncounter.patient_id == patient.id)):
        raise HTTPException(status_code=400, detail="الكشف المختار لا يخص هذا المريض")
    from app.framework.storage import ensure_room

    await ensure_room(db, len(signature))
    consent = ClinicConsentForm(
        id=str(uuid.uuid4()), tenant_id=current_user.tenant_id, consent_ref=f"CNS-{uuid.uuid4().hex[:6].upper()}",
        patient_id=patient.id, encounter_id=payload.encounter_id or None, kind=payload.kind, title=payload.title.strip(),
        body=payload.body.strip(), signer_name=payload.signer_name.strip(), signer_relation=payload.signer_relation,
        signature_path="", signed_at=datetime.now(UTC), witness_user_id=current_user.id,
        witness_name=(current_user.full_name or current_user.username or "")[:128],
    )
    consent.signature_path = await files.store_private(db, signature, kind="clinic_signature", filename="signature.png",
                                                       content_type="image/png", owner_id=consent.id)
    db.add(consent)
    await audit_log(db, "clinic_consent", "sign", current_user.id, current_user.full_name, None,
                    {"consent_ref": consent.consent_ref, "patient_id": patient.id, "kind": consent.kind},
                    f"توقيع نموذج موافقة ({KINDS_AR[consent.kind]}) للمريض {patient.full_name}: {consent.title}")
    await db.commit()
    return _out(consent)


@router.post("/consents/{consent_id}/revoke")
async def revoke_consent(
    consent_id: str,
    payload: ConsentRevoke,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The patient withdraws the consent: kept with the date and reason, never deleted."""
    _require_clinician(current_user)
    c, _ = await _consent(db, current_user, consent_id)
    if c.revoked_at:
        raise HTTPException(status_code=409, detail="تم سحب هذه الموافقة بالفعل")
    c.revoked_at, c.revoked_by, c.revoke_reason = datetime.now(UTC), current_user.id, payload.reason.strip()
    await audit_log(db, "clinic_consent", "revoke", current_user.id, current_user.full_name, None,
                    {"consent_ref": c.consent_ref, "reason": c.revoke_reason}, f"سحب الموافقة {c.consent_ref}")
    await db.commit()
    return _out(c)


@router.get("/consents/{consent_id}/signature-link")
async def consent_signature_link(
    consent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """A short-lived link to the signature image (routes/media.py serves it)."""
    c, _ = await _consent(db, current_user, consent_id)
    return media.link("signature", c.id, current_user)


def _font_faces() -> str:
    faces = []
    for family, stem in (("Mizan Arabic", "NotoSansArabic"), ("Mizan Latin", "NotoSans")):
        for weight, style in ((400, "Regular"), (700, "Bold")):
            faces.append(f"@font-face {{ font-family: '{family}'; font-weight: {weight}; "
                         f"src: url('{(FONTS / f'{stem}-{style}.ttf').as_uri()}'); }}")
    return "\n".join(faces)


def consent_html(c: ClinicConsentForm, patient, signature: bytes, workspace_name: str) -> str:
    e = lambda v: html.escape(str(v)) if v not in (None, "") else "—"  # noqa: E731
    signed = c.signed_at.astimezone(CAIRO).strftime("%Y-%m-%d %H:%M")
    body = "".join(f"<p>{e(line)}</p>" for line in c.body.splitlines() if line.strip())
    revoked = (f'<div class="revoked">سُحبت هذه الموافقة بتاريخ {c.revoked_at.astimezone(CAIRO).strftime("%Y-%m-%d")}'
               f" — السبب: {e(c.revoke_reason)}</div>") if c.revoked_at else ""
    rows = [("المريض", patient.full_name), ("رقم الملف الطبي", patient.patient_mrn), ("الرقم القومي", patient.national_id),
            ("نوع الموافقة", KINDS_AR.get(c.kind, c.kind)), ("رقم النموذج", c.consent_ref)]
    rows_html = "".join(f"<tr><th>{e(k)}</th><td>{e(v)}</td></tr>" for k, v in rows)
    sig = base64.b64encode(signature).decode()
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>{e(c.consent_ref)}</title>
<style>
{_font_faces()}
@page {{ size: A4; margin: 18mm 16mm; }}
body {{ font-family: 'Mizan Arabic', 'Mizan Latin', sans-serif; color: #262321; font-size: 12.5px; line-height: 1.8; }}
.top {{ display: flex; justify-content: space-between; border-bottom: 2px solid #35151D; padding-bottom: 10px; }}
.brand {{ font-size: 18px; font-weight: 700; color: #35151D; }}
.muted {{ color: #77716E; font-size: 11px; }}
h1 {{ font-size: 18px; margin: 16px 0 6px; }}
table {{ width: 100%; border-collapse: collapse; margin: 8px 0 14px; }}
th, td {{ text-align: start; padding: 6px 10px; border-bottom: 1px solid #EDE6DC; }}
th {{ width: 30%; color: #77716E; font-weight: 400; }}
.body {{ border: 1px solid #EDE6DC; border-radius: 8px; padding: 10px 14px; background: #FCFAF7; }}
.sign {{ display: flex; justify-content: space-between; margin-top: 22px; gap: 24px; }}
.sign div {{ flex: 1; }}
.sign img {{ display: block; max-width: 260px; max-height: 110px; border-bottom: 1px solid #262321; margin: 6px 0; }}
.revoked {{ margin-top: 14px; padding: 8px 12px; border-radius: 6px; background: #FBE9E9; color: #8A1C1C; font-weight: 700; }}
.ltr {{ direction: ltr; unicode-bidi: embed; }}
</style></head><body>
<div class="top"><div><div class="brand">{e(workspace_name)}</div><div class="muted">نموذج موافقة مستنيرة</div></div>
<div style="text-align:end"><div class="muted">تاريخ التوقيع</div><div class="ltr">{signed}</div></div></div>
<h1>{e(c.title)}</h1>
<table>{rows_html}</table>
<div class="body">{body}</div>
<div class="sign">
  <div><div class="muted">توقيع {e(RELATIONS_AR.get(c.signer_relation, c.signer_relation))}</div>
    <img src="data:image/png;base64,{sig}" alt="التوقيع"><div>{e(c.signer_name)}</div></div>
  <div><div class="muted">الشاهد (الطاقم الطبي)</div><div style="margin-top:40px">{e(c.witness_name)}</div></div>
</div>
{revoked}
</body></html>"""


@router.get("/consents/{consent_id}/pdf")
async def consent_pdf(
    consent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The signed consent as a PDF (Arabic, RTL, with the signature), or a printable page where the
    server can't render PDFs (printing.fallback)."""
    from app.platform.printing.fallback import pdf_or_page
    from app.platform.tenancy.models import Tenant

    c, how = await _consent(db, current_user, consent_id)
    patient = await patient_or_404(db, current_user.tenant_id, c.patient_id)
    signature = await files.read_private(c.signature_path)
    workspace = await db.scalar(select(Tenant.name).where(Tenant.id == current_user.tenant_id)) or "ميزان"
    content, media_type, ext = await pdf_or_page(consent_html(c, patient, signature, workspace))
    await access.log_access(db, current_user, "consent_pdf", how, c.patient_id, 1)
    return Response(content, media_type=media_type, headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(f'{c.consent_ref}.{ext}')}",
        "Cache-Control": "private, no-store",
    })
