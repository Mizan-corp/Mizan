"""Private append-only actuals, no stock, payroll, accounting or invoice effects.

Caller checks grants and feature/module activation, binds tenant, commits or rolls
back. Cost/selling write and read flags are independently resolved permissions.
"""
import hashlib,json
from uuid import UUID,uuid5,NAMESPACE_URL
from fastapi import HTTPException
from sqlalchemy import select,text
from .models import HelpdeskExecutionRevision
from app.dependencies import verify_warehouse_access
from .actuals_contract import ExecutionWorksheet,summarize
from app.activities.maintenance.modules.field_service.models import FsmWorkOrder,FsmTechnician
from app.activities.property.modules.real_estate.models import RecMaintenanceTicket,RecUnit,RecProperty
from app.activities.general.modules.inventory.models.product import Product
from app.activities.general.modules.inventory.models.warehouse import Warehouse

async def source_row(db,user,source,source_id):
    model={'field_service':FsmWorkOrder,'real_estate':RecMaintenanceTicket}[source]
    row=(await db.execute(select(model).where(model.tenant_id==user.tenant_id,model.id==str(source_id)).with_for_update())).scalar_one_or_none()
    if row is None:raise HTTPException(404,'Work source not found')
    if source=='real_estate':
        unit=(await db.execute(select(RecUnit).where(RecUnit.tenant_id==user.tenant_id,RecUnit.id==row.unit_id).with_for_update())).scalar_one_or_none()
        if unit is None:raise HTTPException(404,'Source unit not found')
        if not await db.scalar(select(RecProperty.id).where(RecProperty.tenant_id==user.tenant_id,RecProperty.id==unit.property_id)):raise HTTPException(404,'Source property not found')
    return row

async def save_actuals(db,*,user,payload:ExecutionWorksheet,can_write_cost=False,can_write_selling=False):
    if not user.tenant_id:raise HTTPException(403,'Workspace required')
    identity=uuid5(NAMESPACE_URL,f'mizan:helpdesk:actuals:v1:{user.tenant_id}:{payload.operation_id}')
    await db.execute(text('SELECT pg_advisory_xact_lock(:k)'),{'k':int.from_bytes(identity.bytes[:8],signed=True)})
    await source_row(db,user,payload.source_module,payload.source_id)
    data=payload.model_dump(mode='json');fingerprint=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
    prior=(await db.execute(select(HelpdeskExecutionRevision).where(HelpdeskExecutionRevision.id==identity,HelpdeskExecutionRevision.tenant_id==user.tenant_id))).scalar_one_or_none()
    if prior:
        if prior.fingerprint!=fingerprint or prior.user_id!=user.id:raise HTTPException(409,'Operation already used')
        return {'revision':prior.revision,'replayed':True,'stock_posted':False,'accounting_posted':False}
    current=(await db.execute(select(HelpdeskExecutionRevision).where(HelpdeskExecutionRevision.tenant_id==user.tenant_id,HelpdeskExecutionRevision.source_module==payload.source_module,HelpdeskExecutionRevision.source_id==str(payload.source_id)).order_by(HelpdeskExecutionRevision.revision.desc()).limit(1))).scalar_one_or_none()
    if (current.revision if current else 0)!=payload.expected_revision:raise HTTPException(409,'Worksheet changed; reload before saving')
    previous=current.payload['lines'] if current else []
    for stored in previous:
        if stored.get('warehouse_id'):await verify_warehouse_access(db,user,UUID(stored['warehouse_id']))
    prefix=data['lines'][:len(previous)]
    if len(prefix)!=len(previous):raise HTTPException(409,'Existing actuals cannot be removed')
    for submitted,stored in zip(prefix,previous):
        expected=dict(stored)
        for key,allowed in [('cost',can_write_cost),('selling',can_write_selling)]:
            if not allowed:
                if submitted[key] is not None:raise HTTPException(403,'Restricted snapshot cannot be supplied')
                expected[key]=None
        if submitted!=expected:raise HTTPException(409,'Existing actuals cannot be rewritten; append correction')
    data['lines'][:len(previous)]=previous
    new=data['lines'][len(previous):]
    if not new:raise HTTPException(422,'Append an actual or correction')
    labels=dict(current.resource_labels) if current else {}
    for line in new:
        info={}
        if line['cost'] is not None and not can_write_cost:raise HTTPException(403,'Cost snapshot permission required')
        if line['selling'] is not None and not can_write_selling:raise HTTPException(403,'Selling snapshot permission required')
        if line['technician_id']:
            technician=await db.scalar(select(FsmTechnician.tech_name).where(FsmTechnician.tenant_id==user.tenant_id,FsmTechnician.id==line['technician_id']))
            if technician is None:raise HTTPException(404,'Technician not found')
            info['technician']=technician
        if line['product_id']:
            product=(await db.execute(select(Product).where(Product.tenant_id==user.tenant_id,Product.id==UUID(line['product_id']),Product.is_active==True))).scalar_one_or_none()
            if product is None:raise HTTPException(404,'Active product not found')
            info['product']=product.name
            if product.unit!=line['unit']:raise HTTPException(422,'Record product base unit; unit conversion is not implicit')
        if line['warehouse_id']:
            location=await db.scalar(select(Warehouse.name).where(Warehouse.tenant_id==user.tenant_id,Warehouse.id==UUID(line['warehouse_id']),Warehouse.is_active==True))
            if location is None:raise HTTPException(404,'Active warehouse not found')
            info['warehouse']=location
            await verify_warehouse_access(db,user,UUID(line['warehouse_id']))
        labels[line['line_id']]=info
    row=HelpdeskExecutionRevision(id=identity,tenant_id=user.tenant_id,source_module=payload.source_module,source_id=str(payload.source_id),revision=payload.expected_revision+1,user_id=user.id,fingerprint=fingerprint,payload=data,resource_labels=labels)
    db.add(row);await db.flush()
    return {'revision':row.revision,'replayed':False,'stock_posted':False,'accounting_posted':False}

async def read_actuals(db,*,user,source,source_id,can_view_cost=False,can_view_selling=False):
    await source_row(db,user,source,source_id)
    row=(await db.execute(select(HelpdeskExecutionRevision).where(HelpdeskExecutionRevision.tenant_id==user.tenant_id,HelpdeskExecutionRevision.source_module==source,HelpdeskExecutionRevision.source_id==str(source_id)).order_by(HelpdeskExecutionRevision.revision.desc()).limit(1))).scalar_one_or_none()
    if row is None:return {'revision':0,'worksheet':None,'stock_posted':False,'accounting_posted':False}
    sheet=ExecutionWorksheet.model_validate(row.payload)
    # A request view is not a grant to inspect a restricted source location.
    # Fail closed for a mixed-location worksheet rather than leak its costs or
    # misrepresent a partial projection as complete.
    for line in sheet.lines:
        if line.warehouse_id:await verify_warehouse_access(db,user,line.warehouse_id)
    data=sheet.model_dump(mode='json')
    labels=row.resource_labels
    for line in data['lines']:
        if not can_view_cost:line.pop('cost',None)
        if not can_view_selling:line.pop('selling',None)
    return {'revision':row.revision,'worksheet':data,'resource_labels':labels,'summary':summarize(sheet,can_view_cost=can_view_cost,can_view_selling=can_view_selling)}
