"""Authenticated first-party draft-page set installer, no public runtime."""
from fastapi import APIRouter,Depends
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import get_db
from app.dependencies import require_perm
from .page_kits import kit_catalog,install_kit,make_pages
from .router import _detail
from .tech_kit import TECH_KIT,theme as tech_theme

router=APIRouter(prefix='/site/page-kits',tags=['Site draft page kits'])
class InstallIn(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    kit_id:str=Field(min_length=1,max_length=80)
    prefix:str=Field(min_length=1,max_length=40)

@router.get('')
async def catalog(_=Depends(require_perm('site.manage'))):
    return kit_catalog()

@router.get('/preview')
async def preview(prefix:str,kit_id:str='catalog-pages-v0',_=Depends(require_perm('site.manage'))):
    pages=make_pages(prefix,kit_id)
    return {'items':pages,**({'suggested_theme':tech_theme(prefix)} if kit_id==TECH_KIT else {})}

@router.post('/install',status_code=201)
async def install(data:InstallIn,db:AsyncSession=Depends(get_db),_=Depends(require_perm('site.manage'))):
    rows=await install_kit(db,data.kit_id,data.prefix)
    return {'items':[_detail(row) for row in rows]}
