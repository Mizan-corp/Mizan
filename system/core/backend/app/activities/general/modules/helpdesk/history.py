"""Narrow controlled-event history, never an export of the shared audit log."""
import json
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select
from app.framework.activation import get_active_modules
from app.activities.maintenance.modules.field_service.models import FsmWorkOrder
from app.activities.property.modules.real_estate.models import RecMaintenanceTicket
from app.platform.audit.models import AuditLog

async def source_history(db, *, user, source: str, source_id: str):
    models={'field_service':FsmWorkOrder,'real_estate':RecMaintenanceTicket}
    if source not in models:raise HTTPException(404,'Work source not found')
    if source not in set(await get_active_modules(db)):raise HTTPException(403,'Work source is inactive')
    model=models[source]
    row=(await db.execute(select(model).where(model.id==source_id,model.tenant_id==user.tenant_id))).scalar_one_or_none()
    if row is None:raise HTTPException(404,'Work not found')
    result={'source_module':source,'source_id':source_id,'current_native_status':row.status,
        'events':[],'coverage':'controlled_events_only','legacy_history_available':False,
        'limit':100,'truncated':False,'unreadable_events':0}
    # Include only each source-specific controlled event contract. Never infer
    # chronology from current status or search unrelated audit entities.
    try:entity_id=UUID(source_id)
    except ValueError:return result
    rows=(await db.execute(select(AuditLog).where(AuditLog.tenant_id==user.tenant_id,
        AuditLog.entity_type==('helpdesk_fsm_work' if source=='field_service' else 'helpdesk_property_request'),AuditLog.entity_id==entity_id,
        AuditLog.action_type==('complete' if source=='field_service' else 'create')).order_by(AuditLog.created_at.desc(),AuditLog.id).limit(101))).scalars().all()
    result['truncated']=len(rows)>100
    for event in rows[:100]:
        try:
            data=json.loads(event.details)
            if (data.get('contract_version')!=1 or data.get('source_module')!=source
                or data['result']['source_id']!=source_id):raise ValueError('Unrecognized event contract')
            if source=='field_service':
                if data['result']['source_status']!='completed' or data['from_status'] not in {'dispatched','on_site','parts_needed'}:raise ValueError('Unrecognized completion')
                before=data['from_status'];after='completed'
            else:
                if data['result']['source_status']!='open':raise ValueError('Unrecognized creation')
                before=None;after='open'
            result['events'].append({'id':str(event.id),'recorded_at':event.created_at.isoformat(),
                'action':event.action_type,'from_status':before,'to_status':after})
        except (ValueError,TypeError,KeyError,AttributeError):result['unreadable_events']+=1
    return result
