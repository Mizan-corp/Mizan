"""Internal FSM completion primitive. Not exposed by any route.

The future caller must independently enforce effective manage/source grants,
module activation and tenant binding. No property transition is invented here.
"""
import hashlib
import json
from uuid import UUID, uuid5, NAMESPACE_URL
from fastapi import HTTPException
from sqlalchemy import select
from app.activities.maintenance.modules.field_service.models import FsmWorkOrder, FsmTechnician
from app.platform.audit.models import AuditLog

COMPLETABLE = frozenset({'dispatched', 'on_site', 'parts_needed'})

def operation_identity(tenant_id, source_id, operation_id):
    return uuid5(NAMESPACE_URL, f'mizan:helpdesk:fsm-completion:v1:{tenant_id}:{source_id}:{operation_id}')

async def complete_fsm(db, *, user, source_id: str, operation_id: UUID,
                       expected_status: str, completion_notes: str):
    """Within caller transaction: lock, replay-safe native effect and audit.

    Never commits. Caller owns rollback on every error and final commit. Notes
    and client/site details never enter the returned acknowledgement or audit.
    """
    if not user.tenant_id:
        raise HTTPException(403, 'Workspace required')
    try:
        source_uuid = UUID(source_id)
    except (ValueError, TypeError):
        raise HTTPException(422, 'Native work ID must be a valid UUID')
    if expected_status not in COMPLETABLE or not completion_notes.strip() or len(completion_notes) > 5000:
        raise HTTPException(422, 'Known expected native status and completion notes required')
    row = (await db.execute(select(FsmWorkOrder).where(
        FsmWorkOrder.id == source_id, FsmWorkOrder.tenant_id == user.tenant_id).with_for_update())).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, 'Work order not found')
    audit_id = operation_identity(user.tenant_id, source_id, operation_id)
    fingerprint = hashlib.sha256(json.dumps({'expected_status': expected_status,
        'completion_notes': completion_notes}, sort_keys=True).encode()).hexdigest()
    prior = (await db.execute(select(AuditLog).where(AuditLog.id == audit_id,
        AuditLog.tenant_id == user.tenant_id))).scalar_one_or_none()
    if prior:
        details = json.loads(prior.details)
        if details.get('fingerprint') != fingerprint or str(prior.user_id) != str(user.id):
            raise HTTPException(409, 'Operation ID already used for another command')
        return {**details['result'], 'replayed': True}
    if row.status != expected_status:
        raise HTTPException(409, 'Native work state changed; reload before completing')
    technicians = (await db.execute(select(FsmTechnician).where(
        FsmTechnician.tenant_id == user.tenant_id,
        FsmTechnician.tech_name == row.assigned_technician).with_for_update())).scalars().all()
    # A name is not a stable technician FK. Do not choose between duplicates or
    # silently drop the expected native technician effect when none exists.
    if len(technicians) != 1:
        raise HTTPException(409, 'Assigned technician must resolve uniquely before completion')
    technician = technicians[0]
    row.status = 'completed'
    row.completion_notes = completion_notes
    technician.jobs_completed_today += 1
    technician.live_status = 'available'
    result = {'source_module': 'field_service', 'source_id': source_id,
              'source_status': 'completed', 'operation_id': str(operation_id)}
    db.add(AuditLog(id=audit_id,tenant_id=user.tenant_id,action_type='complete',
        entity_type='helpdesk_fsm_work',entity_id=source_uuid,user_id=user.id,
        user_name=user.full_name,details=json.dumps({'contract_version':1,
            'source_module':'field_service','from_status':expected_status,
            'fingerprint':fingerprint,'result':result})))
    await db.flush()
    return {**result, 'replayed': False}
