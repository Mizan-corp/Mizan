"""Studio picker E2E backend: the REAL site router (pages + media + settings), real
auth dependencies and real tenancy on the migrated scratch Postgres, plus the same
/uploads static mount app.factory's serve_files adds. Test-only assembly, like the
existing studio-harness serve_http.py - never mounted in a real app."""
import os
import sys

sys.path.insert(0, os.environ.get("STUDIO_BACKEND_ROOT", "/tmp/mizan-push/system/core/backend"))
os.environ["DATABASE_URL"] = os.environ.get("STUDIO_E2E_DB", "postgresql://postgres@127.0.0.1:5544/mizan_studio_e2e")
os.environ.setdefault("SECRET_KEY", "studio-e2e-secret")
os.environ.setdefault("UPLOAD_DIR", "/tmp/studio-e2e-uploads")

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.models.registry import load_all_models
from app.platform.tenancy.context import install_tenancy_events
from app.platform.site.router import router as site_router

load_all_models()
install_tenancy_events()

app = FastAPI(title="Studio picker E2E")
app.include_router(site_router)
os.makedirs(os.environ["UPLOAD_DIR"], exist_ok=True)
app.mount("/uploads", StaticFiles(directory=os.environ["UPLOAD_DIR"]), name="uploads")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
