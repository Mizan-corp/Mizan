"""Explicit private execution worksheet routes, no posting effects."""
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import get_db
from app.dependencies import require_perm
from app.framework.activation import get_active_modules
from app.framework.loader import registry
from app.platform.permissions.access import can
from .actuals_contract import ExecutionWorksheet
from .actuals import read_actuals,save_actuals

router=APIRouter()
async def actuals_allowed(source:Literal['field_service','real_estate'],db:AsyncSession=Depends(get_db),
        user=Depends(require_perm('helpdesk:work:view')),_=Depends(require_perm('operations'))):
    if source not in set(await get_active_modules(db)):raise HTTPException(403,'Work source is inactive')
    if (await registry.get_settings(db,'helpdesk'))['values'].get('work_actuals') is not True:raise HTTPException(409,'Execution actuals are disabled')
    return user

def cost_scope(user):
    return can(user,'helpdesk:cost:manage') and can(user,'inventory','purchases','reports')
def selling_scope(user):
    return can(user,'helpdesk:selling:manage')

@router.get('/work/{source}/{source_id}/actuals')
async def get_actuals(source:Literal['field_service','real_estate'],source_id:str,
        db:AsyncSession=Depends(get_db),user=Depends(actuals_allowed)):
    from uuid import UUID
    try:source_id=str(UUID(source_id))
    except ValueError:raise HTTPException(422,'Native source ID must be UUID')
    return await read_actuals(db,user=user,source=source,source_id=source_id,
        can_view_cost=cost_scope(user),can_view_selling=selling_scope(user))

@router.post('/work/{source}/{source_id}/actuals')
async def post_actuals(source:Literal['field_service','real_estate'],source_id:str,payload:ExecutionWorksheet,
        db:AsyncSession=Depends(get_db),user=Depends(actuals_allowed),
        _=Depends(require_perm('helpdesk:work:record'))):
    if payload.source_module!=source or str(payload.source_id)!=source_id:raise HTTPException(422,'Worksheet source does not match route')
    active=set(await get_active_modules(db))
    if any(x.product_id for x in payload.lines) and 'inventory' not in active:raise HTTPException(403,'Inventory source is inactive')
    if any(x.technician_id for x in payload.lines) and 'field_service' not in active:raise HTTPException(403,'Technician source is inactive')
    try:
        result=await save_actuals(db,user=user,payload=payload,
            can_write_cost=cost_scope(user),can_write_selling=selling_scope(user))
        await db.commit();return result
    except Exception:
        await db.rollback();raise

@router.get('/work/{source}/{source_id}/actuals-choices')
async def actuals_choices(source:Literal['field_service','real_estate'],source_id:str,
        db:AsyncSession=Depends(get_db),user=Depends(actuals_allowed),
        _=Depends(require_perm('helpdesk:work:record'))):
    from sqlalchemy import select
    from uuid import UUID
    from .actuals import source_row
    from app.activities.maintenance.modules.field_service.models import FsmTechnician
    from app.activities.general.modules.inventory.models.product import Product
    from app.activities.general.modules.inventory.models.warehouse import Warehouse
    from app.platform.auth.models.user import user_warehouses
    try:source_id=str(UUID(source_id))
    except ValueError:raise HTTPException(422,'Native source ID must be UUID')
    await source_row(db,user,source,source_id)
    active=set(await get_active_modules(db));result={'technicians':[],'products':[],'warehouses':[],'truncated':[],'inventory_active':'inventory' in active}
    if 'field_service' in active:
        rows=(await db.execute(select(FsmTechnician.id,FsmTechnician.tech_name).where(FsmTechnician.tenant_id==user.tenant_id).order_by(FsmTechnician.tech_name,FsmTechnician.id).limit(101))).all()
        result['technicians']=[{'id':r.id,'name':r.tech_name} for r in rows[:100]]
        if len(rows)>100:result['truncated'].append('technicians')
    if 'inventory' in active:
        rows=(await db.execute(select(Product.id,Product.name,Product.unit).where(Product.tenant_id==user.tenant_id,Product.is_active==True).order_by(Product.name,Product.id).limit(101))).all()
        result['products']=[{'id':str(r.id),'name':r.name,'unit':r.unit} for r in rows[:100]]
        if len(rows)>100:result['truncated'].append('products')
        query=select(Warehouse.id,Warehouse.name).where(Warehouse.tenant_id==user.tenant_id,Warehouse.is_active==True)
        if not user.is_manager and not can(user,'supervise'):query=query.where(Warehouse.id.in_(select(user_warehouses.c.warehouse_id).where(user_warehouses.c.user_id==user.id)))
        rows=(await db.execute(query.order_by(Warehouse.name,Warehouse.id).limit(101))).all()
        result['warehouses']=[{'id':str(r.id),'name':r.name} for r in rows[:100]]
        if len(rows)>100:result['truncated'].append('warehouses')
    return result
