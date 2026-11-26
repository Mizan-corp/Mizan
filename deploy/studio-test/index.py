import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core.config import settings
from app.factory import create_app
from system_api.router import router
from website_api.routers import public_pages, uploads
_app=create_app(title="Mizan Test API",routers=[router,public_pages.router],create_tables=False,serve_files=True)
# Production serves uploads from two origins: the ERP origin (session gate) and the website
# origin (anonymous, referenced-public-assets only). This test host has ONE origin and both
# routers claim GET /uploads/{path}, so dispatch like the two origins would: a request with no
# session cookie is anonymous and gets the website origin's reference gate; a request carrying
# a session cookie gets the ERP origin's session gate (which still enforces it fully).
_public=create_app(title="Mizan Test Public Uploads",routers=[uploads.router],create_tables=False,serve_files=False)
async def app(scope,receive,send):
    if scope["type"] in ("http","websocket"):
        path=scope.get("path","")
        if path.startswith("/api"):
            scope=dict(scope);scope["path"]=path[4:] or "/";scope["root_path"]="/api";path=scope["path"]
        headers=dict(scope.get("headers") or [])
        if path.startswith("/uploads/") and b"access_token=" not in (headers.get(b"cookie") or b""):
            await _public(scope,receive,send)
            return
    await _app(scope,receive,send)
