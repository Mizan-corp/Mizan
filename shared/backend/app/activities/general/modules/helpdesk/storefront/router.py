"""Helpdesk-owned explicit website opt-in. No service offering chosen by default."""
import hashlib, json
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import select
from app.db.base import get_db
from app.dependencies import require_perm
from app.framework.activation import get_active_modules
from app.platform.tenancy.context import current_tenant_id
from app.platform.tenancy.models import Tenant
from app.platform.settings.models import StoreSetting
from app.activities.general.modules.helpdesk.models import HelpdeskOffering
from .provider import SETTING_KEY, SCHEMA_V1, publication_ids, service_policy, SourceUnavailable

router = APIRouter(prefix='/site/module-settings/helpdesk', tags=['Website module settings'])


class PublicationIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_token: str
    # Explicit acknowledgement of the disclosure wording the client showed. The
    # writer only accepts the CURRENT wording version: a stale cached client is
    # refused, never silently upgraded (same guard as inventory cards).
    consent_version: str
    offerings: list[UUID] = Field(max_length=200)
    show_description: StrictBool
    show_starting_price: StrictBool


def token(raw):
    return hashlib.sha256(json.dumps([str(current_tenant_id.get()), raw]).encode()).hexdigest()


async def read(db):
    if current_tenant_id.get() is None or 'helpdesk' not in await get_active_modules(db):
        raise HTTPException(422, 'Help Desk unavailable.')
    row = await db.scalar(select(StoreSetting).where(
        StoreSetting.tenant_id == current_tenant_id.get(), StoreSetting.key == SETTING_KEY))
    return row, row.value if row else None


@router.get('')
async def get_publication(db=Depends(get_db), _=Depends(require_perm('site.manage')),
                          __=Depends(require_perm('helpdesk:view', 'helpdesk:manage'))):
    row, raw = await read(db)
    try:
        policy = service_policy(raw)
    except SourceUnavailable:
        raise HTTPException(422, 'Stored services selection is invalid.') from None
    return {'value': {'offerings': [str(x) for x in policy['offerings']],
                      'show_description': policy['show_description'],
                      'show_starting_price': policy['show_starting_price'],
                      'schema': policy['schema']}, 'edit_token': token(raw)}


@router.put('')
async def put_publication(data: PublicationIn, db=Depends(get_db), _=Depends(require_perm('site.manage')),
                          __=Depends(require_perm('helpdesk:manage'))):
    tid = current_tenant_id.get()
    if tid is None:
        raise HTTPException(422, 'Explicit workspace required.')
    # New saves stamp v1: the first wording that names the description and
    # starting-price display fields. Older rows keep their recorded scope.
    if data.consent_version != SCHEMA_V1:
        raise HTTPException(409, 'Website consent wording changed. Reload before saving.')
    await db.execute(select(Tenant.id).where(Tenant.id == tid).with_for_update())
    row, raw = await read(db)
    if token(raw) != data.expected_token:
        raise HTTPException(409, 'Website services selection changed. Reload before saving.')
    value = {'schema': SCHEMA_V1, 'offerings': [str(x) for x in data.offerings],
             'show_description': data.show_description, 'show_starting_price': data.show_starting_price}
    try:
        ids = publication_ids(json.dumps(value))
    except SourceUnavailable:
        raise HTTPException(422, 'Invalid bounded website services selection.') from None
    if ids:
        found = set((await db.execute(select(HelpdeskOffering.id).where(
            HelpdeskOffering.tenant_id == tid,
            HelpdeskOffering.id.in_(ids),
            HelpdeskOffering.is_active.is_(True)))).scalars())
        if found != set(ids):
            raise HTTPException(422, 'Selected service records unavailable in this workspace.')
    encoded = json.dumps(value, sort_keys=True)
    if row is None:
        db.add(StoreSetting(tenant_id=tid, key=SETTING_KEY, value=encoded))
    else:
        row.value = encoded
    await db.commit()
    return {'value': {'offerings': value['offerings'],
                      'show_description': data.show_description,
                      'show_starting_price': data.show_starting_price,
                      'schema': SCHEMA_V1}, 'edit_token': token(encoded)}


@router.get('/choices')
async def choices(db=Depends(get_db), _=Depends(require_perm('site.manage')),
                  __=Depends(require_perm('helpdesk:view', 'helpdesk:manage'))):
    await read(db)
    rows = (await db.execute(
        select(HelpdeskOffering.id, HelpdeskOffering.name)
        .where(HelpdeskOffering.tenant_id == current_tenant_id.get(),
               HelpdeskOffering.is_active.is_(True))
        .order_by(HelpdeskOffering.name, HelpdeskOffering.id).limit(201))).all()
    return {'offerings': {'items': [{'id': str(key), 'name': name} for key, name in rows[:200]],
                          'truncated': len(rows) > 200}}
