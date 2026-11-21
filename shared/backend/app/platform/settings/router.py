import logging
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import get_current_user, require_perm
from app.platform.auth.models.user import User
from app.platform.settings.designer import router as designer_router

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])
router.include_router(designer_router)  # the screen builder (ADR-006 phase 5)

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
    """The workspace's logo, and square PWA icons made from it (files service, #114)."""
    import io

    from PIL import Image

    from app.framework import files

    contents, img = await _read_image(db, file)
    logo_url = await files.store(db, contents, kind="logo", filename=file.filename, content_type=file.content_type)
    icons: dict[str, str] = {}
    try:
        w, h = img.size
        side = min(w, h)
        square = img.crop(((w - side) // 2, (h - side) // 2, (w - side) // 2 + side, (h - side) // 2 + side))
        for size in (192, 512):
            buf = io.BytesIO()
            square.resize((size, size), Image.LANCZOS).save(buf, "PNG")
            icons[str(size)] = await files.store(db, buf.getvalue(), kind="logo_icon", owner_id=str(size),
                                                 filename="icon.png", content_type="image/png")
    except Exception:
        logger.warning("could not make PWA icons from the logo", exc_info=True)
    await _upsert_setting(db, "logo_url", logo_url)
    for size, url in icons.items():
        await _upsert_setting(db, f"logo_icon_{size}", url)
    await db.commit()
    return {"logo_url": logo_url}


@router.post("/upload-cover")
async def upload_cover(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm("settings")),
):
    """The sign-in page's cover image (files service, #114)."""
    from app.framework import files

    contents, _ = await _read_image(db, file)
    url = await files.store(db, contents, kind="cover", filename=file.filename, content_type=file.content_type)
    await _upsert_setting(db, "login_cover_url", url)
    await db.commit()
    return {"cover_url": url}


async def _read_image(db: AsyncSession, file: UploadFile):
    """An uploaded image, checked: type, size, storage quota, and that it really is an image."""
    import io

    from PIL import Image

    from app.framework.storage import ensure_room

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, "نوع الملف غير مدعوم. الأنواع المسموحة: JPEG, PNG, GIF, WebP")
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_SIZE:
        raise HTTPException(400, "حجم الملف يتجاوز 5 ميجابايت")
    await ensure_room(db, len(contents))  # storage quota (ADR-006 D3)
    try:
        Image.open(io.BytesIO(contents)).verify()
        img = Image.open(io.BytesIO(contents))
        img.load()
    except Exception:
        raise HTTPException(400, "الملف ليس صورة صالحة") from None
    return contents, img


async def _upsert_setting(db: AsyncSession, key: str, value: Any) -> None:
    from app.platform.settings.models import StoreSetting
    row = (await db.execute(select(StoreSetting).where(StoreSetting.key == key))).scalar_one_or_none()
    if row:
        row.value = value
    else:
        db.add(StoreSetting(key=key, value=value))


@router.get("/manifest.json", include_in_schema=False)
async def pwa_manifest(db: AsyncSession = Depends(get_db)):
    """Dynamic PWA manifest using logo from settings. The request carries no sign-in, so no workspace is
    bound: the login role would read every workspace's rows (RLS bypassed) and show whichever came
    first. Mizan's own branding is served then; the app's real manifest is the static
    manifest.webmanifest."""
    import os

    from app.platform.tenancy.context import current_tenant_id
    rows = [] if current_tenant_id.get() is None else (await db.execute(text(
        "SELECT key, value FROM store_settings WHERE key IN ('store_name','logo_url','logo_icon_192','logo_icon_512',"
        "'theme_color','theme_primary','theme_bg')"))).fetchall()
    s = {r.key: r.value for r in rows}
    name = s.get("store_name") or "ميزان"
    logo = s.get("logo_url") or ""
    theme_color = (s.get("theme_primary") or s.get("theme_color") or "#35151D").strip()
    background_color = (s.get("theme_bg") or "#FAF6F0").strip()
    icons = []
    if s.get("logo_icon_192") and s.get("logo_icon_512"):
        icons.append({"src": s["logo_icon_192"], "sizes": "192x192", "type": "image/png", "purpose": "any"})
        icons.append({"src": s["logo_icon_512"], "sizes": "512x512", "type": "image/png", "purpose": "any maskable"})
    elif logo:
        if logo.startswith("/"):  # a logo uploaded before the files service: icons named after it
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
async def get_settings(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    """The signed-in workspace's store settings (without modules' own). It used to be public: without a sign-in no workspace is
    bound, so it returned every workspace's settings merged (the login role bypasses RLS)."""
    import json as _json

    from app.platform.settings.models import StoreSetting
    result = await db.execute(select(StoreSetting))
    out = {}
    for row in result.scalars().all():
        if row.key.startswith("mod_settings_"):
            continue  # modules' settings hold secrets; /modules/{id}/settings serves them under `settings`
        try:
            out[row.key] = _json.loads(row.value) if row.value and row.value.startswith(('[', '{')) else row.value
        except (ValueError, _json.JSONDecodeError):
            logger.warning("Failed to parse setting %s: %s", row.key, row.value)
            out[row.key] = row.value
    return out


@router.put("")
async def update_settings(data: dict[str, Any], db: AsyncSession = Depends(get_db), _=Depends(require_perm("settings"))):
    import json as _json

    from app.platform.settings.models import StoreSetting
    items = data.get("settings") if isinstance(data.get("settings"), dict) else data
    items = await _check_vat_settings(db, dict(items))
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


VAT_KEYS = ("vat_registered", "prices_include_vat", "tax_number")


async def _check_vat_settings(db: AsyncSession, items: dict) -> dict:
    """The VAT settings (ADR-014 D6), checked: the tax number is 9 digits (dashes and spaces are
    dropped), the two switches are stored as "true"/"false", and VAT registration needs a tax number
    (sent now or already saved)."""
    from app.platform.settings import vat

    if not any(k in items for k in VAT_KEYS):
        return items
    if "tax_number" in items:
        try:
            items["tax_number"] = vat.clean_tax_number(items["tax_number"])
        except ValueError as e:
            raise HTTPException(422, str(e)) from None
    for key in ("vat_registered", "prices_include_vat"):
        if key in items:
            items[key] = "true" if str(items[key]).strip().lower() in ("1", "true", "yes", "on") else "false"
    if items.get("vat_registered") == "true":
        number = items["tax_number"] if "tax_number" in items else (await vat.vat_settings(db)).tax_number
        if not number:
            raise HTTPException(422, "أدخل رقم التسجيل الضريبي قبل تفعيل ضريبة القيمة المضافة")
    return items


@router.get("/vat")
async def get_vat_settings(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    """The workspace's VAT settings and the tax codes with their rates (ADR-014 D6), for the screens
    that show or compute VAT (the point of sale, the product form, the settings screen)."""
    from app.platform.settings import vat

    s = await vat.vat_settings(db)
    return {"vat_registered": s.registered, "prices_include_vat": s.prices_include_vat,
            "tax_number": s.tax_number, "tax_number_display": vat.format_tax_number(s.tax_number),
            "codes": [{"code": c, "label": vat.TAX_LABELS[c], "rate": float(r)} for c, r in vat.TAX_RATES.items()],
            "default_code": vat.DEFAULT_TAX_CODE}


@router.get("/product-options")
async def get_product_options(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    """Return sizes, companies, materials, units lists."""
    import json as _json

    from app.platform.settings.models import StoreSetting
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

    from app.platform.settings.models import StoreSetting
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


# ── The workspace's activity profile and its fields (ADR-006 phase 4) ─────────────────────────

class FieldIn(BaseModel):
    definition: dict[str, Any] = {}
    hidden: bool = False
    position: int = 0


@router.get("/workspace-profile")
async def workspace_profile(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    """What the app adapts to: the activity, its variants, its words and the records' fields."""
    from app.framework import fields as F
    from app.framework import variants
    from app.framework.hooks import workspace_activity

    activity_id = await workspace_activity(db)
    act = variants.activity(activity_id)
    return {
        "activity": act.get("id") or activity_id,
        "activity_name": act.get("name"),
        "variants": variants.variants_for(activity_id),
        "terms": variants.terms_for(activity_id),
        "fields": {r: await F.fields_for(db, r, activity_id) for r in F.RECORDS},
    }


@router.get("/fields/{record}")
async def list_fields(record: str, db: AsyncSession = Depends(get_db), _: User = Depends(require_perm("designer"))):
    """A record's fields, hidden ones included (for editing)."""
    from app.framework import fields as F
    from app.framework.hooks import workspace_activity

    if record not in F.RECORDS:
        raise HTTPException(404, "سجل غير معروف")
    return await F.fields_for(db, record, await workspace_activity(db), include_hidden=True)


@router.put("/fields/{record}/{key}")
async def save_field(record: str, key: str, data: FieldIn, db: AsyncSession = Depends(get_db),
                     _: User = Depends(require_perm("designer"))):
    """Add a field of the workspace's own, or change (relabel, require, hide) a variant's field."""
    from app.framework import fields as F
    from app.framework.hooks import workspace_activity

    if record not in F.RECORDS:
        raise HTTPException(404, "سجل غير معروف")
    if not F.KEY.match(key):
        raise HTTPException(422, "مفتاح الحقل: حروف إنجليزية صغيرة وأرقام و _ فقط")
    activity_id = await workspace_activity(db)
    from app.framework.layouts import forms

    if key in {f["key"] for f in (forms().get(record) or {}).get("fields", [])}:
        raise HTTPException(422, "هذا المفتاح مستخدم لحقل أساسي في النموذج")
    base = {f["key"]: f for f in F.variant_fields(record, activity_id)}.get(key)
    definition = F.check_definition({**(base or {}), **data.definition})
    if base is None and not definition.get("label"):
        raise HTTPException(422, "اسم الحقل مطلوب")
    row = (await db.execute(select(F.WorkspaceField).where(F.WorkspaceField.record == record,
                                                            F.WorkspaceField.key == key))).scalar_one_or_none()
    if row is None:
        row = F.WorkspaceField(record=record, key=key)
        db.add(row)
    row.definition, row.hidden, row.position = definition, data.hidden, data.position
    await db.commit()
    return [f for f in await F.fields_for(db, record, activity_id, include_hidden=True) if f["key"] == key][0]


@router.delete("/fields/{record}/{key}", status_code=204)
async def reset_field(record: str, key: str, db: AsyncSession = Depends(get_db),
                      _: User = Depends(require_perm("designer"))):
    """Remove the workspace's change (a variant's field goes back to its default) or its own field
    (values already saved stay on the records)."""
    await db.execute(text("DELETE FROM workspace_fields WHERE record = :r AND key = :k"), {"r": record, "k": key})
    await db.commit()



@router.get("/storage")
async def storage(refresh: bool = False, db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("settings"))):
    """The workspace's storage: used, the plan's limit, and the analysis by module (ADR-006 D3)."""
    from app.framework.storage import usage

    out = await usage(db, user.tenant_id, refresh=refresh)
    await db.commit()
    return out

