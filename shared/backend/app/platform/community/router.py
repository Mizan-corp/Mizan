"""Community modules: the app's screens for their records (ADR-007 D2). Always available: what a
user may open is decided per entity by the module's declared permissions (service.may_use)."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import get_current_user
from app.platform.auth.models.user import User
from app.platform.community import service

router = APIRouter(prefix="/community", tags=["Community modules"])


@router.get("/menu")
async def menu(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """The installed modules' screens this user may open."""
    return {"items": await service.menu_items(db, user)}


@router.get("/{module_id}/{entity}")
async def entity_definition(module_id: str, entity: str, db: AsyncSession = Depends(get_db),
                            user: User = Depends(get_current_user)):
    m, e = await service.module_entity(db, user, module_id, entity)
    references = {}
    for f in e["fields"]:
        if f.get("type") == "reference" and f["to"] in m.entities:
            references[f["to"]] = {"name": m.entities[f["to"]].get("name"), "title": m.entities[f["to"]].get("title")}
    return {"module": {"id": m.module_id, "name": m.manifest.get("name"), "name_en": m.manifest.get("name_en"),
                       "icon": m.manifest.get("icon"), "version": m.version, "developer": m.developer},
            "entity": e, "references": references,
            "title": next((i["label"] for i in m.manifest.get("menu") or [] if i.get("entity") == entity), None)}


@router.get("/{module_id}/{entity}/options/{key}")
async def reference_options(module_id: str, entity: str, key: str, q: str | None = None,
                            db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    m, e = await service.module_entity(db, user, module_id, entity)
    return {"items": await service.reference_options(db, m, e, key, q)}


@router.get("/{module_id}/{entity}/records")
async def list_records(module_id: str, entity: str, q: str | None = None, page: int = Query(1, ge=1),
                       db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    m, e = await service.module_entity(db, user, module_id, entity)
    return await service.list_records(db, m, e, q, page)


@router.post("/{module_id}/{entity}/records", status_code=201)
async def create_record(module_id: str, entity: str, values: dict[str, Any] = Body(...),
                        db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    m, e = await service.module_entity(db, user, module_id, entity)
    return service.record_out(await service.create_record(db, m, e, values, user.id))


@router.get("/{module_id}/{entity}/records/{record_id}")
async def get_record(module_id: str, entity: str, record_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)):
    m, e = await service.module_entity(db, user, module_id, entity)
    r = service.record_out(await service.get_record(db, m, e, record_id))
    return {**r, "labels": await service.labels_for(db, m, e, [r])}


@router.put("/{module_id}/{entity}/records/{record_id}")
async def update_record(module_id: str, entity: str, record_id: uuid.UUID, values: dict[str, Any] = Body(...),
                        db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    m, e = await service.module_entity(db, user, module_id, entity)
    r = await service.get_record(db, m, e, record_id)
    return service.record_out(await service.update_record(db, m, e, r, values))


@router.delete("/{module_id}/{entity}/records/{record_id}", status_code=204)
async def delete_record(module_id: str, entity: str, record_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    m, e = await service.module_entity(db, user, module_id, entity)
    await service.delete_record(db, await service.get_record(db, m, e, record_id))
