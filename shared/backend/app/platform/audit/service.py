"""Central audit logging service."""
import json
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.tenancy.context import current_tenant_id


async def log(
    db: AsyncSession,
    entity_type: str,
    action: str,
    user_id: uuid.UUID | None = None,
    user_name: str | None = None,
    entity_id: uuid.UUID | None = None,
    changes: dict | None = None,
    note: str | None = None,
):
    # Write only columns the canonical model and migration suite guarantee
    # (action_type/details/reason); fresh databases carry no other shape.
    tid = current_tenant_id.get()
    details = json.dumps(changes) if changes else None
    if tid is not None:
        await db.execute(text("""
            INSERT INTO audit_log (tenant_id, entity_type, entity_id, action_type, user_id, user_name, details, reason)
            VALUES (:tid, :etype, :eid, :atype, :uid, :uname, :det, :why)
        """), {
            "tid": tid,
            "etype": entity_type,
            "eid": entity_id,
            "atype": action,
            "uid": user_id,
            "uname": user_name,
            "det": details,
            "why": note,
        })
    else:
        await db.execute(text("""
            INSERT INTO audit_log (entity_type, entity_id, action_type, user_id, user_name, details, reason)
            VALUES (:etype, :eid, :atype, :uid, :uname, :det, :why)
        """), {
            "etype": entity_type,
            "eid": entity_id,
            "atype": action,
            "uid": user_id,
            "uname": user_name,
            "det": details,
            "why": note,
        })
