"""Community modules: the app's screens for their records (ADR-007 D2). Always available: what a
user may open is decided per entity by the module's declared permissions (service.may_use)."""
from __future__ import annotations

import uuid
from typing import Any

import json

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import get_current_user, require_perm
from app.platform.auth.models.user import User
from app.platform.community import service

router = APIRouter(prefix="/community", tags=["Community modules"])


async def _read_package(file: UploadFile):
    from app.framework import package as mzm

    data = await file.read(mzm.MAX_BYTES + 1)
    try:
        return mzm.verify(data)
    except mzm.PackageError as e:
        raise HTTPException(422, f"تعذر قبول الحزمة: {e}") from None


async def _installed_row(db: AsyncSession, module_id: str):
    from sqlalchemy import select

    from app.platform.community.models import CommunityModule

    return await db.scalar(select(CommunityModule).where(CommunityModule.module_id == module_id))


@router.get("/modules")
async def installed_modules(db: AsyncSession = Depends(get_db), _: User = Depends(require_perm("community.manage"))):
    return {"items": [service.installed_out(m) for m in await service.installed(db)]}


@router.post("/packages/inspect")
async def inspect_package(file: UploadFile = File(...), db: AsyncSession = Depends(get_db),
                          _: User = Depends(require_perm("community.manage"))):
    """Verify a .mzm and say what it would add and may access (nothing is installed)."""
    pkg = await _read_package(file)
    return service.summary(pkg, await _installed_row(db, pkg.manifest["id"]))


@router.post("/packages/install")
async def install_package(file: UploadFile = File(...), approved_scopes: str = Form("[]"),
                          db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("community.manage"))):
    pkg = await _read_package(file)
    try:
        approved = json.loads(approved_scopes)
    except ValueError:
        raise HTTPException(422, "approved_scopes must be a JSON list") from None
    row = await service.install(db, pkg, user.id, approved if isinstance(approved, list) else [])
    return service.installed_out(row)


@router.delete("/modules/{module_id}", status_code=204)
async def uninstall_module(module_id: str, delete_records: bool = False, db: AsyncSession = Depends(get_db),
                           _: User = Depends(require_perm("community.manage"))):
    await service.uninstall(db, module_id, delete_records=delete_records)


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
