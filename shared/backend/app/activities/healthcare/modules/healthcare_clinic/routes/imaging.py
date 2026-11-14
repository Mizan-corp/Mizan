"""Medical images (#44): X-ray, ultrasound, CT, MRI… attached to a patient (and an encounter).

Uploading and viewing need a doctor or nurse who reaches the patient's record; files go to the
private store (framework.files.store_private) and are served only through short-lived signed
links (media.py, routes/media.py), which re-check access and log every read. Accepted: JPEG,
PNG, WebP (checked by their magic bytes, not the browser's word) and DICOM (the "DICM" marker,
.dcm), at most MAX_BYTES. DICOM isn't rendered in the browser (that needs a DICOM decoder);
it is listed and downloaded.
"""
from __future__ import annotations

import os
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.healthcare.modules.healthcare_clinic import media
from app.activities.healthcare.modules.healthcare_clinic import service as access
from app.activities.healthcare.modules.healthcare_clinic.models import ClinicEncounter, ClinicImage
from app.activities.healthcare.modules.healthcare_clinic.routes.charts import patient_or_404
from app.activities.healthcare.modules.healthcare_clinic.routes.media import register
from app.db.base import get_db
from app.dependencies import get_current_user
from app.framework import files
from app.platform.audit.service import log as audit_log
from app.platform.auth.models.user import User
from app.platform.permissions.access import can

router = APIRouter()

MAX_BYTES = 50 * 1024 * 1024
MODALITIES = ("XR", "US", "CT", "MRI", "other")
DICOM = "application/dicom"
EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", DICOM: ".dcm"}


def sniff(head: bytes, filename: str) -> str | None:
    """The file's real type from its first bytes: one of EXTENSIONS, or None."""
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[128:132] == b"DICM":
        return DICOM
    if filename.lower().endswith(".dcm") and len(head) >= 8:
        # Old DICOM files without the preamble start with a (0008,xxxx) group tag.
        return DICOM if head[:2] == b"\x08\x00" else None
    return None


async def _read_limited(upload: UploadFile) -> bytes:
    chunks, size = [], 0
    while chunk := await upload.read(1024 * 1024):
        size += len(chunk)
        if size > MAX_BYTES:
            raise HTTPException(status_code=413, detail="حجم الصورة يتجاوز الحد المسموح (50 ميجابايت)")
        chunks.append(chunk)
    return b"".join(chunks)


def _out(img: ClinicImage) -> dict:
    return {k: getattr(img, k) for k in ("id", "patient_id", "encounter_id", "modality", "content_type", "size",
                                         "original_name", "notes", "uploaded_by_name", "created_at")} | {
        "is_dicom": img.content_type == DICOM, "uploaded_by": str(img.uploaded_by) if img.uploaded_by else None}


def _require_clinician(user: User) -> None:
    if not access.is_clinician(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="الصور الطبية للأطباء وطاقم التمريض")


async def _image(db: AsyncSession, user: User, image_id: str) -> tuple[ClinicImage, str]:
    img = (await db.execute(select(ClinicImage).where(ClinicImage.id == image_id,
                                                      ClinicImage.tenant_id == user.tenant_id))).scalar_one_or_none()
    if not img:
        raise HTTPException(status_code=404, detail="الصورة غير موجودة")
    return img, await access.require_clinical_access(db, user, img.patient_id)


async def _image_media(db: AsyncSession, record_id: str):
    img = await db.get(ClinicImage, record_id)
    if not img:
        raise HTTPException(404, "الملف غير موجود")
    name = img.original_name or f"image{EXTENSIONS.get(img.content_type, '')}"
    return img.patient_id, img.file_path, img.content_type, name, "image"


register("image", _image_media)


@router.post("/patients/{patient_id}/images")
async def upload_image(
    patient_id: str,
    file: UploadFile = File(...),
    modality: Literal["XR", "US", "CT", "MRI", "other"] = Form("other"),
    encounter_id: str | None = Form(None),
    notes: str = Form("", max_length=2000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_clinician(current_user)
    patient = await patient_or_404(db, current_user.tenant_id, patient_id)
    await access.require_clinical_access(db, current_user, patient.id)
    if encounter_id and not await db.scalar(select(ClinicEncounter.id).where(
            ClinicEncounter.id == encounter_id, ClinicEncounter.patient_id == patient.id)):
        raise HTTPException(status_code=400, detail="الكشف المختار لا يخص هذا المريض")
    data = await _read_limited(file)
    if not data:
        raise HTTPException(status_code=400, detail="الملف فارغ")
    original = os.path.basename(file.filename or "")[:255]
    kind = sniff(data[:132], original)
    if kind is None:
        raise HTTPException(status_code=415, detail="نوع الملف غير مدعوم. المسموح: JPEG وPNG وWebP وDICOM (.dcm)")
    from app.framework.storage import ensure_room

    await ensure_room(db, len(data))
    img = ClinicImage(id=str(uuid.uuid4()), tenant_id=current_user.tenant_id, patient_id=patient.id,
                      encounter_id=encounter_id or None, modality=modality, file_path="", content_type=kind, size=len(data),
                      original_name=original, notes=notes.strip(), uploaded_by=current_user.id,
                      uploaded_by_name=(current_user.full_name or current_user.username or "")[:128])
    img.file_path = await files.store_private(db, data, kind="clinic_image", filename=f"image{EXTENSIONS[kind]}",
                                              content_type=kind, owner_id=img.id)
    db.add(img)
    await audit_log(db, "clinic_image", "upload", current_user.id, current_user.full_name, None,
                    {"image_id": img.id, "patient_id": patient.id, "modality": modality, "size": len(data)},
                    f"رفع صورة طبية ({modality}) للمريض {patient.full_name}")
    await db.commit()
    return _out(img) | media.link("image", img.id, current_user)


@router.get("/patients/{patient_id}/images")
async def list_images(
    patient_id: str,
    encounter_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The patient's images, newest first, each with a short-lived link (the list is logged; each
    file opened through its link is logged again)."""
    patient = await patient_or_404(db, current_user.tenant_id, patient_id)
    how = await access.require_clinical_access(db, current_user, patient.id)
    q = select(ClinicImage).where(ClinicImage.tenant_id == current_user.tenant_id, ClinicImage.patient_id == patient.id)
    if encounter_id:
        q = q.where(ClinicImage.encounter_id == encounter_id)
    rows = (await db.execute(q.order_by(ClinicImage.created_at.desc()))).scalars().all()
    await access.log_access(db, current_user, "images", how, patient.id, len(rows))
    return [_out(img) | media.link("image", img.id, current_user) for img in rows]


@router.get("/images/{image_id}/link")
async def image_link(
    image_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    img, _ = await _image(db, current_user, image_id)
    return media.link("image", img.id, current_user)


@router.delete("/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_image(
    image_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Removing a wrongly attached image: its uploader, or a doctor who reaches the record."""
    _require_clinician(current_user)
    img, _ = await _image(db, current_user, image_id)
    if img.uploaded_by != current_user.id and not can(current_user, "clinic:doctor"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="يحذف الصورة من رفعها أو الطبيب المعالج")
    await files.remove(db, url=img.file_path)
    await audit_log(db, "clinic_image", "delete", current_user.id, current_user.full_name, None,
                    {"image_id": img.id, "patient_id": img.patient_id, "original_name": img.original_name},
                    f"حذف صورة طبية ({img.modality}) {img.original_name}")
    await db.delete(img)
    await db.commit()
