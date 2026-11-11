"""Authorization API under /authz.

One permission system (ADR-006 phase 3): /authz/access/... lists the declared permissions, the
roles (standard and the workspace's own) and positions, and assigns them to users. See
routes_access.py.

The older catalogue API (account types, permission overrides, facility and patient rules,
break-glass, its audit log) was removed: no endpoint enforced any of it (#94 follow-up). Its
tables and rows stay in the database.
"""
from fastapi import APIRouter

from app.platform.permissions.routes_access import router as _access_router

router = APIRouter(prefix="/authz", tags=["Authorization"])
router.include_router(_access_router)
