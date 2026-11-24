import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core.config import settings
from app.factory import create_app
from system_api.router import router
from website_api.routers import public_pages
_app=create_app(title="Mizan Test API",routers=[router,public_pages.router],create_tables=False,serve_files=True)
async def app(scope,receive,send):
    if scope["type"] in ("http","websocket") and scope.get("path","").startswith("/api"):
        scope=dict(scope);scope["path"]=scope["path"][4:] or "/";scope["root_path"]="/api"
    await _app(scope,receive,send)
