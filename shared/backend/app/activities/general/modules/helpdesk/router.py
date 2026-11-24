"""Private ERP catalog only. Not public projection, request intake or payment."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import get_db
from app.dependencies import require_perm
from app.framework.activation import require_module
from app.framework.loader import registry
import json
from app.platform.audit.models import AuditLog
from .models import HelpdeskOffering
from .schemas import OfferingCreate, OfferingArchive

router = APIRouter(prefix="/helpdesk", tags=["Help Desk"], dependencies=[Depends(require_module("helpdesk"))])

async def catalog_enabled(db: AsyncSession = Depends(get_db),
                          _=Depends(require_perm("helpdesk:view", "helpdesk:manage"))):
    values = (await registry.get_settings(db, "helpdesk"))["values"]
    if values.get("service_catalog") is not True:
        raise HTTPException(409, "Service catalog is disabled. Existing records are preserved.")


def audit(db, user, row, action, details):
    # Use the actual declared audit schema. Shared service currently targets old columns.
    db.add(AuditLog(tenant_id=user.tenant_id, action_type=action, entity_type="helpdesk_offering",
                    entity_id=row.id, user_id=user.id, user_name=user.full_name,
                    details=json.dumps(details)))


def project(row):
    return {"id": str(row.id), "name": row.name, "description": row.description,
            "starting_amount": str(row.starting_amount), "currency": row.currency,
            "price_kind": "starting_at", "is_active": row.is_active}

@router.get("/offerings", dependencies=[Depends(catalog_enabled)])
async def list_offerings(db: AsyncSession = Depends(get_db), user=Depends(require_perm("helpdesk:view"))):
    rows = (await db.execute(select(HelpdeskOffering).where(HelpdeskOffering.tenant_id == user.tenant_id)
                            .order_by(HelpdeskOffering.created_at.desc()).limit(200))).scalars().all()
    return {"items": [project(row) for row in rows], "limit": 200}

@router.post("/offerings", status_code=201, dependencies=[Depends(catalog_enabled)])
async def create_offering(payload: OfferingCreate, db: AsyncSession = Depends(get_db),
                          user=Depends(require_perm("helpdesk:manage"))):
    if not user.tenant_id:
        raise HTTPException(403, "Workspace required")
    row = HelpdeskOffering(tenant_id=user.tenant_id, **payload.model_dump())
    db.add(row)
    await db.flush()
    result = project(row)
    audit(db, user, row, "create", {"price_kind": "starting_at", "currency": row.currency})
    await db.commit()
    return result

@router.patch("/offerings/{offering_id}/archive", dependencies=[Depends(catalog_enabled)])
async def archive_offering(offering_id: UUID, payload: OfferingArchive,
                           db: AsyncSession = Depends(get_db), user=Depends(require_perm("helpdesk:manage"))):
    row = (await db.execute(select(HelpdeskOffering).where(HelpdeskOffering.id == offering_id,
                           HelpdeskOffering.tenant_id == user.tenant_id).with_for_update())).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Service not found")
    before = row.is_active
    row.is_active = payload.is_active
    result = project(row)
    audit(db, user, row, "archive" if not row.is_active else "restore",
          {"is_active": {"before": before, "after": row.is_active}})
    await db.commit()
    return result
