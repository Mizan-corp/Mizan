"""Inventory-owned explicit website opt-in. No product chosen by default."""
import hashlib,json
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field,StrictBool
from sqlalchemy import select
from app.db.base import get_db
from app.dependencies import require_perm
from app.framework.activation import get_active_modules
from app.platform.tenancy.context import current_tenant_id
from app.platform.tenancy.models import Tenant
from app.platform.settings.models import StoreSetting
from app.activities.general.modules.inventory.models.product import Product,Category
from .provider import SETTING_KEY,SCHEMA,publication_ids,SourceUnavailable
router=APIRouter(prefix='/site/module-settings/inventory',tags=['Website module settings'])
class PublicationIn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_token:str
    products:list[UUID]=Field(max_length=200)
    categories:list[UUID]=Field(max_length=200)

def token(raw):return hashlib.sha256(json.dumps([str(current_tenant_id.get()),raw]).encode()).hexdigest()
async def read(db):
    if current_tenant_id.get() is None or 'inventory' not in await get_active_modules(db):raise HTTPException(422,'Inventory unavailable.')
    row=await db.scalar(select(StoreSetting).where(StoreSetting.tenant_id==current_tenant_id.get(),StoreSetting.key==SETTING_KEY));return row,row.value if row else None
@router.get('')
async def get_publication(db=Depends(get_db),_=Depends(require_perm('site.manage')),__=Depends(require_perm('inventory'))):
    row,raw=await read(db)
    try:value=publication_ids(raw)
    except SourceUnavailable:raise HTTPException(422,'Stored catalog selection is invalid.') from None
    return {'value':{k:[str(x) for x in v] for k,v in value.items()},'edit_token':token(raw)}
@router.put('')
async def put_publication(data:PublicationIn,db=Depends(get_db),_=Depends(require_perm('site.manage')),__=Depends(require_perm('inventory'))):
    tid=current_tenant_id.get()
    if tid is None:raise HTTPException(422,'Explicit workspace required.')
    await db.execute(select(Tenant.id).where(Tenant.id==tid).with_for_update())
    row,raw=await read(db)
    if token(raw)!=data.expected_token:raise HTTPException(409,'Website catalog selection changed. Reload before saving.')
    value={'schema':SCHEMA,'products':[str(x) for x in data.products],'categories':[str(x) for x in data.categories]}
    try:ids=publication_ids(json.dumps(value))
    except SourceUnavailable:raise HTTPException(422,'Invalid bounded website selection.') from None
    for kind,model in [('products',Product),('categories',Category)]:
        selected=ids[kind]
        if not selected:continue
        query=select(model.id).where(model.tenant_id==tid,model.id.in_(selected))
        if kind=='products':query=query.where(Product.is_active.is_(True))
        found=set((await db.execute(query)).scalars())
        if found!=set(selected):raise HTTPException(422,'Selected catalog records unavailable in this workspace.')
    encoded=json.dumps(value,sort_keys=True)
    if row is None:db.add(StoreSetting(tenant_id=tid,key=SETTING_KEY,value=encoded))
    else:row.value=encoded
    await db.commit()
    return {'value':{k:v for k,v in value.items() if k!='schema'},'edit_token':token(encoded)}

@router.get('/choices')
async def choices(db=Depends(get_db),_=Depends(require_perm('site.manage')),__=Depends(require_perm('inventory'))):
    await read(db)
    tid=current_tenant_id.get();out={}
    for kind,model in [('products',Product),('categories',Category)]:
        query=select(model.id,model.name).where(model.tenant_id==tid)
        if kind=='products':query=query.where(Product.is_active.is_(True))
        rows=(await db.execute(query.order_by(model.name,model.id).limit(201))).all()
        out[kind]={'items':[{'id':str(key),'name':name} for key,name in rows[:200]],'truncated':len(rows)>200}
    return out

class CardPublicationIn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_token:str
    # Explicit acknowledgement of the disclosure wording the client showed. The
    # writer only accepts the CURRENT wording version: a stale cached client
    # (older or missing acknowledgement) is refused, never silently upgraded.
    consent_version:str
    products:list[UUID]=Field(max_length=200)
    show_price:StrictBool
    show_image:StrictBool
    currency:str|None

async def card_read(db):
    from .cards import SETTING_KEY as key
    await read(db)
    row=await db.scalar(select(StoreSetting).where(StoreSetting.tenant_id==current_tenant_id.get(),StoreSetting.key==key))
    return row,row.value if row else None

def card_value(policy):
    return {**policy,'products':[str(x) for x in policy['products']]}

@router.get('/cards')
async def get_cards(db=Depends(get_db),_=Depends(require_perm('site.manage')),__=Depends(require_perm('inventory'))):
    from .cards import stored_policy
    row,raw=await card_read(db)
    try:value=card_value(stored_policy(raw))
    except SourceUnavailable:raise HTTPException(422,'Stored website cards policy is invalid.') from None
    return {'value':value,'edit_token':token(raw)}

@router.put('/cards')
async def put_cards(data:CardPublicationIn,db=Depends(get_db),_=Depends(require_perm('site.manage')),__=Depends(require_perm('inventory'))):
    # New saves stamp v2: wording covers individually bound elements as well
    # as cards and repeating lists. Older rows keep their recorded scope. The
    # save is accepted only when the client explicitly acknowledges the v2
    # wording; a cached older client is refused (409, reload) so its save can
    # never record consent the owner was never shown. The same implicit-upgrade
    # hole existed in the v0->v1 writer and is closed by this guard.
    from .cards import card_policy,SETTING_KEY as key,SCHEMA_V2 as schema
    tid=current_tenant_id.get()
    if tid is None:raise HTTPException(422,'Explicit workspace required.')
    if data.consent_version!=schema:raise HTTPException(409,'Website consent wording changed. Reload before saving.')
    await db.execute(select(Tenant.id).where(Tenant.id==tid).with_for_update())
    row,raw=await card_read(db)
    if token(raw)!=data.expected_token:raise HTTPException(409,'Website card policy changed. Reload before saving.')
    value={'schema':schema,'products':[str(x) for x in data.products],'show_price':data.show_price,'show_image':data.show_image,'currency':data.currency}
    try:policy=card_policy(json.dumps(value),schema=schema)
    except SourceUnavailable:raise HTTPException(422,'Invalid explicit website card policy.') from None
    if policy['products']:
        found=set((await db.execute(select(Product.id).where(Product.tenant_id==tid,Product.is_active.is_(True),Product.id.in_(policy['products'])))).scalars())
        if found!=set(policy['products']):raise HTTPException(422,'Selected website products are unavailable.')
    encoded=json.dumps(value,sort_keys=True)
    if row is None:db.add(StoreSetting(tenant_id=tid,key=key,value=encoded))
    else:row.value=encoded
    await db.commit()
    return {'value':card_value(policy),'edit_token':token(encoded)}
