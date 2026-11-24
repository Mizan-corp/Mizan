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
from .schemas import OfferingCreate, OfferingArchive, FsmCompletion, PropertyRequestCreate

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

@router.get("/work")
async def list_legacy_work(db: AsyncSession = Depends(get_db),
                           user=Depends(require_perm("helpdesk:work:view")),
                           _=Depends(require_perm("operations"))):
    from .work import list_source_work
    return await list_source_work(db, user)

@router.post('/work/field_service/{source_id}/complete')
async def complete_field_service(source_id: str, payload: FsmCompletion,
        db: AsyncSession = Depends(get_db),
        user=Depends(require_perm('helpdesk:work:complete')),
        _read=Depends(require_perm('helpdesk:work:view')),
        _source=Depends(require_perm('operations')),
        _module=Depends(require_module('field_service'))):
    from .completion import complete_fsm
    values = (await registry.get_settings(db, 'helpdesk'))['values']
    if values.get('work_completion') is not True:
        raise HTTPException(409, 'Field-service work completion is disabled')
    try:
        result = await complete_fsm(db,user=user,source_id=source_id,
            operation_id=UUID(payload.operation_id),expected_status=payload.expected_status,
            completion_notes=payload.completion_notes)
        await db.commit()
        return result
    except Exception:
        await db.rollback()
        raise

@router.get('/work/{source}/{source_id}/history')
async def work_history(source: str, source_id: str,
        db: AsyncSession=Depends(get_db),
        user=Depends(require_perm('helpdesk:work:view')),
        _source=Depends(require_perm('operations'))):
    from .history import source_history
    return await source_history(db,user=user,source=source,source_id=source_id)

async def intake_allowed(db: AsyncSession=Depends(get_db),
        _create=Depends(require_perm('helpdesk:work:create')),
        _read=Depends(require_perm('helpdesk:work:view')),
        _source=Depends(require_perm('operations')),
        _module=Depends(require_module('real_estate'))):
    if (await registry.get_settings(db,'helpdesk'))['values'].get('work_intake') is not True:
        raise HTTPException(409,'Property request intake is disabled')

@router.get('/work/real_estate/units',dependencies=[Depends(intake_allowed)])
async def intake_units(db: AsyncSession=Depends(get_db),user=Depends(require_perm('helpdesk:work:create'))):
    from .intake import unit_choices
    return await unit_choices(db,user)

@router.post('/work/real_estate/requests',status_code=201,dependencies=[Depends(intake_allowed)])
async def property_intake(payload: PropertyRequestCreate,db: AsyncSession=Depends(get_db),
        user=Depends(require_perm('helpdesk:work:create'))):
    from .intake import create_property_request
    try:
        result=await create_property_request(db,user=user,payload=payload)
        await db.commit()
        return result
    except Exception:
        await db.rollback()
        raise
