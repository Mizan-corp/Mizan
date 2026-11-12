"""Server mode: one process and one address for the app and the API.

`/api/*` is the system API, everything else is the built ERP (with the SPA
fallback to index.html). Writes are refused while the licence is expired or
revoked (the workspace stays readable); the install checks in with Mizan Cloud
in the background when it's online.
"""
from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from app.platform.licensing import keys as licensing
from app.core.config import settings
from app.dependencies import get_current_user
from app.platform.auth.models.user import User
from app.onprem import checkin, licence, state

READ_ONLY_DETAIL = {
    "expired": "انتهى ترخيص ميزان على هذا الجهاز. البيانات متاحة للعرض فقط. جدّد الاشتراك من لوحة المالك أو أدخل مفتاح ترخيص جديد.",
    "revoked": "تم إيقاف ترخيص ميزان لهذه النسخة. البيانات متاحة للعرض فقط. تواصل مع الدعم.",
    "missing": "لا يوجد ترخيص لهذه النسخة. أدخل مفتاح الترخيص من لوحة المالك.",
    "invalid": "مفتاح الترخيص غير صالح. أدخل المفتاح من لوحة المالك.",
}

# Signing in and fixing the licence must work while read-only.
ALWAYS_ALLOWED = ("/auth/login", "/auth/logout", "/auth/reauthenticate", "/auth/print-token", "/onprem/")

router = APIRouter(prefix="/onprem", tags=["on-premise"])


@router.get("/status")
async def status():
    lic = licence.current()
    payload = lic.get("payload") or {}
    st = state.read_state()
    return {
        "mode": settings.MIZAN_MODE,
        "workspace": (payload.get("workspace") or {}).get("name"),
        "licence": {"status": lic["status"], "valid_until": lic.get("valid_until"), "days_left": lic.get("days_left")},
        "installation_id": str(state.installation_id()),
        "last_check_in_at": st.get("last_check_in_at"),
        "app_version": checkin.APP_VERSION,
        # Updates (#89): a newer release Mizan offered, and how the last update went.
        "update_available": (st.get("update_available") or {}).get("version"),
        "last_update": st.get("last_update"),
        "ca_certificate": _ca_path() is not None,
    }


def _ca_path() -> Path | None:
    import os

    tls_dir = os.environ.get("MIZAN_TLS_DIR")
    path = Path(tls_dir) / "mizan-ca.crt" if tls_dir else None
    return path if path and path.exists() else None


@router.get("/ca.crt")
async def ca_certificate():
    """LAN installs: the certificate tills install once to trust this server's HTTPS."""
    path = _ca_path()
    if path is None:
        raise HTTPException(status_code=404, detail="No certificate on this install")
    return FileResponse(path, media_type="application/x-x509-ca-cert", filename="mizan-ca.crt")


def _require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="فقط مدير النظام يستطيع تغيير الترخيص")
    return user


class LicenceKey(BaseModel):
    key: str = Field(min_length=10, max_length=8000)


@router.post("/licence")
async def set_licence(body: LicenceKey, _: User = Depends(_require_admin)):
    try:
        payload = licence.accept_key(body.key)
    except licensing.LicenceError as e:
        raise HTTPException(status_code=400, detail=f"مفتاح الترخيص غير مقبول: {e}") from None
    return {"ok": True, "valid_until": payload["valid_until"], "status": licence.current()["status"]}


@router.post("/check-in")
async def check_in_now(_: User = Depends(_require_admin)):
    return await checkin.check_in_once()


def _licence_gate(api: FastAPI) -> None:
    @api.middleware("http")
    async def enforce_licence(request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            path = request.scope.get("path", "")
            root = request.scope.get("root_path", "")
            if root and path.startswith(root):
                path = path[len(root):]
            if not any(path.startswith(p) for p in ALWAYS_ALLOWED):
                lic = licence.current()
                if lic["status"] != "active":
                    return JSONResponse(status_code=403, content={"detail": READ_ONLY_DETAIL[lic["status"]], "code": "licence_read_only"})
        return await call_next(request)


def build_server_app(api: FastAPI) -> FastAPI:
    """Wrap the system API for an on-premise install."""
    api.include_router(router)
    _licence_gate(api)
    web_dir = Path(settings.MIZAN_WEB_DIR).resolve() if settings.MIZAN_WEB_DIR else None

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI):
        async with api.router.lifespan_context(api):  # mounted apps don't get their own lifespan
            task = asyncio.create_task(checkin.run_forever())
            try:
                yield
            finally:
                task.cancel()

    root = FastAPI(title=f"Mizan ({settings.MIZAN_MODE})", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    root.mount("/api", api)

    @root.get("/{path:path}", include_in_schema=False)
    async def web(path: str):
        if web_dir is None or not (web_dir / "index.html").exists():
            return JSONResponse({"detail": "The app isn't installed here (MIZAN_WEB_DIR)."}, status_code=404)
        target = (web_dir / path).resolve()
        if path and target.is_file() and target.is_relative_to(web_dir):
            return FileResponse(target)
        return FileResponse(web_dir / "index.html", headers={"Cache-Control": "no-cache"})

    return root
