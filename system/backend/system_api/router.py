"""System (ERP) API routes: every endpoint the tenant-facing app uses."""
from fastapi import APIRouter

from app.framework.loader import registry
from app.platform.archive.router import router as archive_router
from app.platform.auth.router import router as auth_router
from app.platform.billing.router import router as billing_router
from app.platform.notifications.router import router as notifications_router
from app.platform.permissions.router import router as permissions_router
from app.platform.printing.router import router as printing_router
from app.platform.settings.router import router as settings_router
from app.platform.updates.router import router as updates_router
from system_api.routers import platform as platform_router
from system_api.routers import tenants as tenants_router

router = APIRouter()

# The platform's engines (always on, not modules): app/platform/<engine>/ (ADR-006).
router.include_router(auth_router)
router.include_router(archive_router)
router.include_router(settings_router)
router.include_router(printing_router)
router.include_router(platform_router.router)
router.include_router(tenants_router.router)
router.include_router(notifications_router)
router.include_router(updates_router)
router.include_router(billing_router)
router.include_router(permissions_router)

# Every module's routes come from the one loader: the general modules (the core ERP), the module
# centre (platform/marketplace) and every activity's modules. No module is imported by hand.
for _module_router in registry.get_routers().values():
    router.include_router(_module_router)
