"""Context-preserving property maintenance intake, no dispatch/accounting effects."""
import hashlib,json
from uuid import UUID,uuid5,NAMESPACE_URL
from fastapi import HTTPException
from sqlalchemy import select,text
from app.activities.property.modules.real_estate.models import RecUnit,RecProperty,RecMaintenanceTicket
from app.platform.audit.models import AuditLog

async def unit_choices(db,user):
    rows=(await db.execute(select(RecUnit.id,RecUnit.unit_number,RecProperty.property_name)
        .join(RecProperty,RecUnit.property_id==RecProperty.id)
        .where(RecUnit.tenant_id==user.tenant_id,RecProperty.tenant_id==user.tenant_id)
        .order_by(RecProperty.property_name,RecUnit.unit_number,RecUnit.id).limit(101))).all()
    return {'items':[{'id':r.id,'unit_number':r.unit_number,'property_name':r.property_name} for r in rows[:100]],'truncated':len(rows)>100}

async def create_property_request(db,*,user,payload):
    operation=UUID(payload.operation_id)
    identity=uuid5(NAMESPACE_URL,f'mizan:helpdesk:property-intake:v1:{user.tenant_id}:{operation}')
    # Serialize retries before the source exists. Scoped deterministic lock key.
    lock_key=int.from_bytes(identity.bytes[:8],signed=True)
    await db.execute(text('SELECT pg_advisory_xact_lock(:k)'),{'k':lock_key})
    fingerprint=hashlib.sha256(json.dumps(payload.model_dump(exclude={'operation_id'}),sort_keys=True).encode()).hexdigest()
    prior=(await db.execute(select(AuditLog).where(AuditLog.id==identity,AuditLog.tenant_id==user.tenant_id))).scalar_one_or_none()
    if prior:
        data=json.loads(prior.details)
        if data.get('fingerprint')!=fingerprint or str(prior.user_id)!=str(user.id):raise HTTPException(409,'Operation ID already used')
        return {**data['result'],'replayed':True}
    unit=(await db.execute(select(RecUnit).where(RecUnit.id==payload.unit_id,RecUnit.tenant_id==user.tenant_id).with_for_update())).scalar_one_or_none()
    if unit is None:raise HTTPException(404,'Unit not found')
    prop=(await db.execute(select(RecProperty.id).where(RecProperty.id==unit.property_id,RecProperty.tenant_id==user.tenant_id))).scalar_one_or_none()
    if prop is None:raise HTTPException(404,'Property not found')
    row=RecMaintenanceTicket(id=str(identity),tenant_id=user.tenant_id,unit_id=unit.id,
        ticket_ref='HD-'+identity.hex[:12].upper(),category=payload.category,
        description=payload.description,reported_by=payload.reported_by,
        cost_egp=0.0,is_cam_apportioned=False,status='open')
    db.add(row)
    result={'source_module':'real_estate','source_id':row.id,'reference':row.ticket_ref,'source_status':'open','unit_id':unit.id}
    db.add(AuditLog(id=identity,tenant_id=user.tenant_id,action_type='create',entity_type='helpdesk_property_request',entity_id=identity,user_id=user.id,user_name=user.full_name,
        details=json.dumps({'contract_version':1,'source_module':'real_estate','fingerprint':fingerprint,'result':result})))
    await db.flush()
    return {**result,'replayed':False}
