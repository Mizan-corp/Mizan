"""Explicit website-authored business profile. No legal/invoice settings fallback."""
import json
from sqlalchemy import select
from app.framework.storefront_runtime import Provider,SourceContext,SourceUnavailable
from app.platform.tenancy.context import current_tenant_id
from app.platform.settings.models import StoreSetting
SETTING_KEY='core_website_profile_v0'
SCHEMA='mizan.core-website-profile.experimental.v0'
FIELDS=('display_name','tagline')
CONTRACT={'schema':'mizan.storefront.experimental.v0','module':'core','sources':[{'id':'website_profile','label':'Explicit website business profile','exposure':'public_projection','cardinality':'one','fields':[{'id':name,'label':name.replace('_',' ').title(),'type':'text','semantic':'plain_text','nullable':True,'exposure':'public','elements':['heading','text']} for name in FIELDS]}],'pages':[]}

def profile_projection(raw):
    if raw is None:return {name:None for name in FIELDS}
    try:value=json.loads(raw)
    except (ValueError,TypeError):raise SourceUnavailable('Invalid website profile.') from None
    if not isinstance(value,dict) or set(value)!={'schema',*FIELDS} or value['schema']!=SCHEMA:
        raise SourceUnavailable('Invalid explicit website profile.')
    if any(value[name] is not None and (not isinstance(value[name],str) or len(value[name])>200) for name in FIELDS):
        raise SourceUnavailable('Invalid website profile text.')
    return {name:value[name] for name in FIELDS}

def core_provider(db):
    async def read(context:SourceContext,source:str):
        if current_tenant_id.get()!=context.tenant_id or source!='website_profile':
            raise SourceUnavailable('Website profile unavailable.')
        raw=await db.scalar(select(StoreSetting.value).where(StoreSetting.tenant_id==context.tenant_id,StoreSetting.key==SETTING_KEY))
        return profile_projection(raw)
    return Provider('core',CONTRACT,read,platform_core=True)
