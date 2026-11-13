"""Builds a Mizan FastAPI service.

Every deployable backend (system, website, admin) is assembled here so they
share identical middleware, CORS, CSRF, error handling and health checks, and
differ only in the routers they mount.
"""
import logging
import os
import re
import tempfile
import traceback
from collections.abc import Iterable
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.core.config import settings
from app.platform.tenancy.context import install_tenancy_events
from app.db.base import Base, engine
from app.middleware import add_csrf_middleware
from app.models.registry import load_all_models

logger = logging.getLogger("validation")


def _resolve_writable_dir(path: str) -> str:
    """Return the path if writable, else a writable mirror under /tmp."""
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".wprobe")
        with open(probe, "w") as f:
            f.write("")
        os.remove(probe)
        return path
    except OSError:
        alt = os.path.join(tempfile.gettempdir(), os.path.basename(path.strip(os.sep)))
        os.makedirs(alt, exist_ok=True)
        return alt


def create_app(
    *,
    title: str,
    routers: Iterable[APIRouter],
    create_tables: bool = False,
    serve_files: bool = False,
) -> FastAPI:
    """Create a service app.

    create_tables: run Base.metadata.create_all at startup (outside Vercel).
        Only the system service owns schema bootstrap.
    serve_files: mount /uploads and /updates static directories.
    """
    load_all_models()
    install_tenancy_events()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if create_tables and not os.environ.get("VERCEL"):
            try:
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
                    # Ensure safe_deposit exists in the doc_type_enum (added after initial creation)
                    await conn.execute(text("ALTER TYPE doc_type_enum ADD VALUE IF NOT EXISTS 'safe_deposit'"))
            except Exception as e:
                logging.getLogger("startup").warning("Lifespan DB initialization notice: %s", e)
        from app.framework import package_activities

        package_activities.start()  # developers' activities (ADR-012), once per process
        yield

    app = FastAPI(title=title, version="1.0.0", lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def log_validation_error(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        logger.error("Validation error on %s %s: %s", request.method, request.url.path, errors)
        safe_errors = []
        for e in errors:
            ctx = e.get("ctx", {})
            clean_ctx = {}
            for k, v in ctx.items():
                clean_ctx[k] = str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
            safe_errors.append({**e, "ctx": clean_ctx})
        return JSONResponse(status_code=422, content={"detail": safe_errors})

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        tb = traceback.format_exc()
        logger.error("Unhandled error on %s %s: %s\n%s", request.method, request.url.path, exc, tb)
        origin = request.headers.get("origin")
        headers = {}
        if origin:
            if origin in settings.CORS_ORIGINS or re.match(settings.CORS_ORIGIN_REGEX, origin):
                headers["Access-Control-Allow-Origin"] = origin
                headers["Access-Control-Allow-Credentials"] = "true"
                headers["Access-Control-Allow-Methods"] = "*"
                headers["Access-Control-Allow-Headers"] = "*"
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal Server Error: {str(exc)}", "error_type": exc.__class__.__name__},
            headers=headers,
        )

    # CSRF protection (inner)
    add_csrf_middleware(app)

    # CORS (outermost — guarantees headers on all responses, including errors)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_origin_regex=settings.CORS_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        return response

    if serve_files:
        upload_dir = _resolve_writable_dir(settings.UPLOAD_DIR)
        settings.UPLOAD_DIR = upload_dir
        app.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")
        updates_dir = _resolve_writable_dir(os.environ.get("UPDATES_DIR", "./updates"))
        app.mount("/updates", StaticFiles(directory=updates_dir), name="updates")

    for router in routers:
        app.include_router(router)

    @app.get("/")
    async def root():
        return {"name": title, "docs": "/docs", "health": "/health"}

    @app.get("/health")
    async def health():
        from app.db.base import AsyncSessionLocal

        try:
            async with AsyncSessionLocal() as sess:
                await sess.execute(text("SELECT 1"))
            return {"status": "ok", "database": "connected"}
        except Exception:
            return {"status": "degraded", "database": "disconnected"}

    return app
