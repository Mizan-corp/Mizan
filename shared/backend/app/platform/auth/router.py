"""Sign-in and users: /auth (workspace sign-in, sessions), /account (owners' sign-in on the
app's /login), /users (the workspace's users)."""
from fastapi import APIRouter

from app.platform.auth.routes import auth, owner_login, users

router = APIRouter()
router.include_router(auth.router)
router.include_router(owner_login.router)
router.include_router(users.router)
