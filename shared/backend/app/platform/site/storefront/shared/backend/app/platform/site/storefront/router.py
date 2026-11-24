"""Authenticated Studio data discovery/resolution, not a public catalog endpoint."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import get_db
from app.dependencies import require_perm
from app.framework.activation import get_active_modules
from app.framework.storefront_runtime import ProviderRegistry, SourceContext, SourceUnavailable, ProjectionInvalid
from app.platform.tenancy.context import current_tenant_id
from .provider import site_provider

router = APIRouter(prefix='/site/data', tags=['Site data'])


class ResolveIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    binding: dict
    # Native target key, not an arbitrary client-supplied semantic descriptor.
    target: str
    language: str = 'en'


async def context(db: AsyncSession, language: str) -> SourceContext:
    try:
        return SourceContext(current_tenant_id.get(), language, frozenset(await get_active_modules(db)))
    except SourceUnavailable:
        raise HTTPException(422, 'Explicit workspace and supported language required.') from None


@router.get('')
async def discover(db: AsyncSession = Depends(get_db), _=Depends(require_perm('site.manage'))):
    ctx=await context(db, 'en')
    return {'schema':'mizan.storefront.experimental.v0','modules':ProviderRegistry((site_provider(db),)).discover(ctx)}


@router.post('/resolve')
async def resolve(data: ResolveIn, db: AsyncSession = Depends(get_db), _=Depends(require_perm('site.manage'))):
    if data.target != 'heading.text':
        raise HTTPException(422, 'Only native heading text is supported by this runtime slice.')
    ctx=await context(db, data.language)
    target={'type':'text','semantic':'plain_text','cardinality':'one','element':'heading'}
    try:
        value=await ProviderRegistry((site_provider(db),)).resolve(ctx,data.binding,target)
    except SourceUnavailable:
        raise HTTPException(422,'Source unavailable or incompatible.') from None
    except ProjectionInvalid:
        raise HTTPException(503,'Source projection could not be verified.') from None
    return {'value':value,'hidden':value is None}


class PreviewIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tree: dict
    language: str = 'en'
    device: str = 'desktop'


@router.post('/preview')
async def preview(data: PreviewIn, db: AsyncSession = Depends(get_db), _=Depends(require_perm('site.manage'))):
    from app.platform.site import service
    from app.platform.site.render import render_page
    from app.framework.manifest import page_problems
    from .bindings import resolve_tree
    if data.device not in ('desktop','tablet','mobile'):
        raise HTTPException(422,'Unsupported preview device.')
    await service.check_bound_tree(db,data.tree)
    ctx=await context(db,data.language)
    try:
        tree=await resolve_tree(data.tree,ProviderRegistry((site_provider(db),)),ctx,lambda t:page_problems(t,('en','ar')))
        return {'html':render_page(tree,lang=data.language,device=data.device),'tree':tree}
    except SourceUnavailable:
        raise HTTPException(422,'Page data source unavailable.') from None
    except ProjectionInvalid:
        raise HTTPException(503,'Page data projection could not be verified.') from None
