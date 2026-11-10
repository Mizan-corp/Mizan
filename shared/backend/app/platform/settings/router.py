import logging
import re
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import get_current_user, require_perm
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_UPLOAD_SIZE = 5 * 1024 * 1024


class SettingsUpdate(BaseModel):
    settings: dict[str, Any] | None = None


@router.post("/upload-logo")
async def upload_logo(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm("settings")),
):
    import io
    import os
    import uuid

    from PIL import Image

    from app.core.config import settings as cfg
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, "نوع الملف غير مدعوم. الأنواع المسموحة: JPEG, PNG, GIF, WebP")
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_SIZE:
        raise HTTPException(400, "حجم الملف يتجاوز 5 ميجابايت")
    try:
        img = Image.open(io.BytesIO(contents))
        img.verify()
        img = Image.open(io.BytesIO(contents))
    except Exception:
        raise HTTPException(400, "الملف ليس صورة صالحة") from None
    os.makedirs(cfg.UPLOAD_DIR, exist_ok=True)

    t_prefix = f"tenant_{current_user.tenant_id}_" if current_user.tenant_id else ""
    safe_uid = uuid.uuid4().hex[:8]
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
        ext = ".png"
    dest_name = f"logo_{t_prefix}{safe_uid}{ext}"
    dest = os.path.join(cfg.UPLOAD_DIR, dest_name)
    with open(dest, "wb") as f:
        f.write(contents)
    # Generate square PWA icons from uploaded image
    try:
        w, h = img.size
        size = min(w, h)
        left = (w - size) // 2
        top = (h - size) // 2
        cropped = img.crop((left, top, left + size, top + size))
        for icon_size in (192, 512):
            resized = cropped.resize((icon_size, icon_size), Image.LANCZOS)
            pwa_name = f"logo_{t_prefix}{safe_uid}-{icon_size}x{icon_size}.png"
            resized.save(os.path.join(cfg.UPLOAD_DIR, pwa_name), "PNG")
    except Exception:
        pass
    url = f"/uploads/{dest_name}"
    await _upsert_setting(db, "logo_url", url)
    await db.commit()
    return {"logo_url": url}


@router.post("/upload-cover")
async def upload_cover(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm("settings")),
):
    import io
    import os
    import uuid

    from PIL import Image

    from app.core.config import settings as cfg
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, "نوع الملف غير مدعوم. الأنواع المسموحة: JPEG, PNG, GIF, WebP")
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_SIZE:
        raise HTTPException(400, "حجم الملف يتجاوز 5 ميجابايت")
    try:
        img = Image.open(io.BytesIO(contents))
        img.verify()
    except Exception:
        raise HTTPException(400, "الملف ليس صورة صالحة") from None
    os.makedirs(cfg.UPLOAD_DIR, exist_ok=True)

    t_prefix = f"tenant_{current_user.tenant_id}_" if current_user.tenant_id else ""
    safe_uid = uuid.uuid4().hex[:8]
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
        ext = ".png"
    dest_name = f"cover_{t_prefix}{safe_uid}{ext}"
    dest = os.path.join(cfg.UPLOAD_DIR, dest_name)
    with open(dest, "wb") as f:
        f.write(contents)

    url = f"/uploads/{dest_name}"
    await _upsert_setting(db, "login_cover_url", url)
    await db.commit()
    return {"cover_url": url}


async def _upsert_setting(db: AsyncSession, key: str, value: Any) -> None:
    from app.models.settings import StoreSetting
    row = (await db.execute(select(StoreSetting).where(StoreSetting.key == key))).scalar_one_or_none()
    if row:
        row.value = value
    else:
        db.add(StoreSetting(key=key, value=value))


@router.get("/manifest.json", include_in_schema=False)
async def pwa_manifest(db: AsyncSession = Depends(get_db)):
    """Dynamic PWA manifest using logo from settings."""
    import os
    rows = (await db.execute(text("SELECT key, value FROM store_settings WHERE key IN ('store_name','logo_url','theme_color','theme_primary','theme_bg')"))).fetchall()
    s = {r.key: r.value for r in rows}
    name = s.get("store_name") or "ميزان"
    logo = s.get("logo_url") or ""
    theme_color = (s.get("theme_primary") or s.get("theme_color") or "#35151D").strip()
    background_color = (s.get("theme_bg") or "#FAF6F0").strip()
    icons = []
    if logo:
        if logo.startswith("/"):
            base = os.path.splitext(logo)[0]
            icons.append({"src": f"{base}-192x192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"})
            icons.append({"src": f"{base}-512x512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"})
        else:
            icons.append({"src": logo, "sizes": "any", "type": "image/png", "purpose": "any maskable"})
    if not icons:
        icons = [
            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ]
    from fastapi.responses import JSONResponse
    return JSONResponse({"name": name, "short_name": name[:12], "theme_color": theme_color,
                         "background_color": background_color, "display": "standalone",
                         "start_url": "/", "lang": "ar", "dir": "rtl", "icons": icons})


@router.get("")
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Public endpoint — returns store settings for login page and app."""
    import json as _json

    from app.models.settings import StoreSetting
    result = await db.execute(select(StoreSetting))
    out = {}
    for row in result.scalars().all():
        try:
            out[row.key] = _json.loads(row.value) if row.value and row.value.startswith(('[', '{')) else row.value
        except (ValueError, _json.JSONDecodeError):
            logger.warning("Failed to parse setting %s: %s", row.key, row.value)
            out[row.key] = row.value
    return out


@router.put("")
async def update_settings(data: dict[str, Any], db: AsyncSession = Depends(get_db), _=Depends(require_perm("settings"))):
    import json as _json

    from app.models.settings import StoreSetting
    items = data.get("settings") if isinstance(data.get("settings"), dict) else data
    for key, value in items.items():
        if key == "settings" and isinstance(value, dict):
            continue
        # Store lists/dicts as JSON string
        str_value = _json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else str(value)
        result = await db.execute(select(StoreSetting).where(StoreSetting.key == key))
        row = result.scalar_one_or_none()
        if row:
            row.value = str_value
        else:
            db.add(StoreSetting(key=key, value=str_value))
    await db.commit()
    return {"detail": "Settings updated"}


@router.get("/product-options")
async def get_product_options(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    """Return sizes, companies, materials, units lists."""
    import json as _json

    from app.models.settings import StoreSetting
    keys = ["product_options_sizes", "product_options_companies", "product_options_materials", "product_options_units"]
    result = await db.execute(select(StoreSetting).where(StoreSetting.key.in_(keys)))
    rows = {r.key: r.value for r in result.scalars().all()}
    return {
        "sizes":     _json.loads(rows.get("product_options_sizes", "[]")),
        "companies": _json.loads(rows.get("product_options_companies", "[]")),
        "materials": _json.loads(rows.get("product_options_materials", "[]")),
        "units":     _json.loads(rows.get("product_options_units", "[]")),
    }


@router.put("/product-options")
async def update_product_options(data: dict, db: AsyncSession = Depends(get_db), _=Depends(require_perm("settings"))):
    """Update one or more option lists. Pass {sizes:[...], companies:[...], ...}"""
    import json as _json

    from app.models.settings import StoreSetting
    mapping = {"sizes": "product_options_sizes", "companies": "product_options_companies",
               "materials": "product_options_materials", "units": "product_options_units"}
    for field, db_key in mapping.items():
        if field in data:
            result = await db.execute(select(StoreSetting).where(StoreSetting.key == db_key))
            row = result.scalar_one_or_none()
            val = _json.dumps(data[field], ensure_ascii=False)
            if row:
                row.value = val
            else:
                db.add(StoreSetting(key=db_key, value=val))
    await db.commit()
    return {"detail": "Product options updated"}
