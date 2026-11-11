"""Server-side sign-out (#77).

Tokens stay stateless JWTs, with two ways to end them early:
- signing out puts the token's id (jti) in revoked_tokens until it would have expired;
- a password change or reset sets tokens_valid_after on the user or owner account, which ends
  every token issued before it.
"""
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def sessions_end_now() -> datetime:
    """Tokens issued before this moment are refused (tokens carry a millisecond issue time)."""
    return datetime.now(UTC)


async def ensure_live(db: AsyncSession, payload: dict, valid_after: datetime | None) -> None:
    """Refuse a token that was signed out, or issued before the account's sessions were ended."""
    issued_ms = payload.get("iat_ms") or (int(payload["iat"]) * 1000 if payload.get("iat") else None)
    if valid_after is not None and (issued_ms is None or issued_ms < int(valid_after.timestamp() * 1000)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="انتهت الجلسة، سجّل الدخول من جديد")
    jti = payload.get("jti")
    if jti and await db.scalar(text("SELECT 1 FROM revoked_tokens WHERE jti = :j"), {"j": str(jti)}):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="تم تسجيل الخروج من هذه الجلسة")


async def revoke(db: AsyncSession, payload: dict) -> None:
    """Sign this token out (idempotent). Expired entries are pruned on the way."""
    jti, exp = payload.get("jti"), payload.get("exp")
    if not jti or not exp:
        return
    await db.execute(text("DELETE FROM revoked_tokens WHERE expires_at < now()"))
    await db.execute(text(
        "INSERT INTO revoked_tokens (jti, expires_at) VALUES (:j, to_timestamp(:e)) ON CONFLICT DO NOTHING"
    ), {"j": str(jti), "e": int(exp)})
