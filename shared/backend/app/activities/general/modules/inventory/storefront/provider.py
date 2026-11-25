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
    fields={'name':{'type':'text','semantic':'plain_text','nullable':False,'max_length':200}}
    if source=='products':
        # Optional typed display fields. Declaring them supplies no value:
        # read() fills them only from a v1 display consent (cards.py), which
        # nothing writes until the consent-scope wording change ships.
        fields['price']={'type':'money','semantic':'display_money','nullable':True}
        fields['image']={'type':'media','semantic':'display_media','nullable':True}
    return {'schema':'mizan.collection.experimental.v0','module':'inventory','source':source,'key':'item_key',
            'fields':fields,'max_items':24}

def inventory_providers(db):
    def make(kind,model):
        async def read(context:SourceContext,limit:int):
            if current_tenant_id.get()!=context.tenant_id or 'inventory' not in context.active_modules:
                raise SourceUnavailable('Inventory website source unavailable.')
            raw=await db.scalar(select(StoreSetting.value).where(StoreSetting.tenant_id==context.tenant_id,StoreSetting.key==SETTING_KEY))
            selected=publication_ids(raw)[kind]
            if not selected:return []
            consent=None
            if kind=='products':
                # Absolute import: this module is also loaded standalone by the
                # integration checks (no package context), where a relative
                # import fails. Registered sys.modules entries resolve first.
                from app.activities.general.modules.inventory.storefront.cards import display_consent
                consent=await display_consent(db,context)
            # Do not even select optional fields before explicit v1 opt-in.
            columns=[model.id,model.name]
            if consent is not None and consent['show_price']:columns.append(Product.retail_price)
            if consent is not None and consent['show_image']:columns.append(Product.image_url)
            query=select(*columns).where(model.tenant_id==context.tenant_id,model.id.in_(selected))
            if kind=='products':query=query.where(Product.is_active.is_(True))
            # Stable UUID ordering, no result joins or raw/private row serialization.
            rows=(await db.execute(query.order_by(model.id).limit(limit))).all()
            result=[]
            for row in rows:
                key,name=row[0],row[1]
                if not isinstance(name,str) or not name.strip() or len(name)>200:
                    raise SourceUnavailable('Selected catalog text exceeds reviewed bound.')
                item={'item_key':str(key),'name':name}
                if kind=='products':
                    item['price']=None
                    item['image']=None
                    if consent is not None and str(key) in {str(p) for p in consent['products']}:
                        optional=list(row[2:])
                        if consent['show_price']:
                            from app.framework.storefront_values import money_value
                            item['price']=money_value(optional.pop(0),consent['currency'])
                        if consent['show_image']:
                            url=optional.pop(0)
                            if url:
                                from app.framework.files import WorkspaceFile
                                record=await db.scalar(select(WorkspaceFile.id).where(
                                    WorkspaceFile.tenant_id==context.tenant_id,
                                    WorkspaceFile.kind=='product_image',
                                    WorkspaceFile.owner_id==str(key),
                                    WorkspaceFile.url==url,
                                    WorkspaceFile.content_type.in_(['image/png','image/jpeg','image/gif','image/webp'])))
                                if record is None:
                                    raise SourceUnavailable('Product image provenance unavailable.')
                                from app.framework.storefront_values import media_value
                                item['image']=media_value(url,name,context.tenant_id)
                result.append(item)
            return result
        return CollectionProvider(text_contract(kind),read)
    return (make('products',Product),make('categories',Category))
