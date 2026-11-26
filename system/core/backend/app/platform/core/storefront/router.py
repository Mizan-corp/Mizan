"""Explicit website profile control, guarded separately from ordinary ERP settings."""
import hashlib,json
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict
from sqlalchemy import select
from app.db.base import get_db
from app.dependencies import require_perm
from app.platform.tenancy.context import current_tenant_id
from app.platform.tenancy.models import Tenant
from app.platform.settings.models import StoreSetting
from .provider import SETTING_KEY,SCHEMA,FIELDS,profile_projection,SourceUnavailable
router=APIRouter(prefix='/site/module-settings/core',tags=['Website module settings'])
class ProfileIn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_token:str
    display_name:str|None=None
    tagline:str|None=None

def token(raw):return hashlib.sha256(json.dumps([str(current_tenant_id.get()),raw],ensure_ascii=False).encode()).hexdigest()
async def read(db):
    row=await db.scalar(select(StoreSetting).where(StoreSetting.tenant_id==current_tenant_id.get(),StoreSetting.key==SETTING_KEY))
    raw=row.value if row else None
    return row,raw
@router.get('')
async def get_profile(db=Depends(get_db),_=Depends(require_perm('site.manage')),__=Depends(require_perm('settings'))):
    row,raw=await read(db)
    try:value=profile_projection(raw)
    except SourceUnavailable:raise HTTPException(422,'Stored website profile is invalid.') from None
    return {'value':value,'edit_token':token(raw)}
@router.put('')
async def put_profile(data:ProfileIn,db=Depends(get_db),_=Depends(require_perm('site.manage')),__=Depends(require_perm('settings'))):
    tid=current_tenant_id.get()
    if tid is None:raise HTTPException(422,'Explicit workspace required.')
    await db.execute(select(Tenant.id).where(Tenant.id==tid).with_for_update())
    row,raw=await read(db)
    if token(raw)!=data.expected_token:raise HTTPException(409,'Website profile changed. Reload before saving.')
    value={'schema':SCHEMA,**{name:getattr(data,name) for name in FIELDS}}
    try:clean=profile_projection(json.dumps(value))
    except SourceUnavailable:raise HTTPException(422,'Invalid bounded website profile.') from None
    encoded=json.dumps(value,ensure_ascii=False,sort_keys=True)
    if row is None:db.add(StoreSetting(tenant_id=tid,key=SETTING_KEY,value=encoded))
    else:row.value=encoded
    await db.commit()
    return {'value':clean,'edit_token':token(encoded)}
