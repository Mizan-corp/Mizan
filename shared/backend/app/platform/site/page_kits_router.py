"""Authenticated first-party draft-page set installer, no public runtime."""
from fastapi import APIRouter,Depends
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import get_db
from app.dependencies import require_perm
from .page_kits import kit_catalog,install_kit,make_pages
from .router import _detail

router=APIRouter(prefix='/site/page-kits',tags=['Site draft page kits'])
class InstallIn(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    kit_id:str=Field(min_length=1,max_length=80)
    prefix:str=Field(min_length=1,max_length=40)

@router.get('')
async def catalog(_=Depends(require_perm('site.manage'))):
    return kit_catalog()

@router.get('/preview')
async def preview(prefix:str,_=Depends(require_perm('site.manage'))):
    return {'items':make_pages(prefix)}

@router.post('/install',status_code=201)
async def install(data:InstallIn,db:AsyncSession=Depends(get_db),_=Depends(require_perm('site.manage'))):
    rows=await install_kit(db,data.kit_id,data.prefix)
    return {'items':[_detail(row) for row in rows]}
