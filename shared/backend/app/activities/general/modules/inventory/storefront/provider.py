"""Reviewed opt-in catalog text, local-only. No implicit is_active publication.

The module owns its website allowlist in tenant StoreSetting, default empty. No public
endpoint, settings writer or automatic migration is installed by this source file.
"""
import json
from uuid import UUID
from sqlalchemy import select
from app.framework.storefront_collections import CollectionProvider
from app.framework.storefront_runtime import SourceContext,SourceUnavailable
from app.platform.tenancy.context import current_tenant_id
from app.platform.settings.models import StoreSetting
from app.activities.general.modules.inventory.models.product import Product,Category

SETTING_KEY='inventory_website_publication_v0'
SCHEMA='mizan.inventory-website.experimental.v0'

def publication_ids(raw):
    if raw is None:return {'products':(), 'categories':()}
    try:value=json.loads(raw)
    except (TypeError,ValueError):raise SourceUnavailable('Invalid website catalog selection.') from None
    if not isinstance(value,dict) or set(value)!={'schema','products','categories'} or value['schema']!=SCHEMA:
        raise SourceUnavailable('Invalid website catalog selection.')
    result={}
    for kind in ('products','categories'):
        ids=value[kind]
        if not isinstance(ids,list) or len(ids)>200 or any(not isinstance(x,str) for x in ids):
            raise SourceUnavailable('Invalid bounded website selection.')
        try:parsed=tuple(UUID(x) for x in ids)
        except (ValueError,TypeError):raise SourceUnavailable('Invalid catalog record identity.') from None
        if len(set(parsed))!=len(parsed):raise SourceUnavailable('Duplicate website selection.')
        result[kind]=parsed
    return result

def text_contract(source):
    return {'schema':'mizan.collection.experimental.v0','module':'inventory','source':source,'key':'item_key',
            'fields':{'name':{'type':'text','semantic':'plain_text','nullable':False,'max_length':200}},'max_items':24}

def inventory_providers(db):
    def make(kind,model):
        async def read(context:SourceContext,limit:int):
            if current_tenant_id.get()!=context.tenant_id or 'inventory' not in context.active_modules:
                raise SourceUnavailable('Inventory website source unavailable.')
            raw=await db.scalar(select(StoreSetting.value).where(StoreSetting.tenant_id==context.tenant_id,StoreSetting.key==SETTING_KEY))
            selected=publication_ids(raw)[kind]
            if not selected:return []
            query=select(model.id,model.name).where(model.tenant_id==context.tenant_id,model.id.in_(selected))
            if kind=='products':query=query.where(Product.is_active.is_(True))
            # Stable UUID ordering, no result joins or raw/private row serialization.
            rows=(await db.execute(query.order_by(model.id).limit(limit))).all()
            result=[]
            for key,name in rows:
                if not isinstance(name,str) or not name.strip() or len(name)>200:
                    raise SourceUnavailable('Selected catalog text exceeds reviewed bound.')
                result.append({'item_key':str(key),'name':name})
            return result
        return CollectionProvider(text_contract(kind),read)
    return (make('products',Product),make('categories',Category))
