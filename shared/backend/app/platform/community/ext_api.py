"""The extension API (ADR-007 D4): what a community module's server may do in the workspace that
installed it, with that installation's token and only the scopes the owner approved.

    Authorization: Bearer mzx_...

A public contract: versioned (/ext/v1), documented at dev.allmizan.live/docs, changed only with
deprecation. Lists take `limit` (≤ 200) and `offset`, and return {"items", "total"}.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratelimit import RateLimiter
from app.db.base import get_db
from app.platform.community import service
from app.platform.community.models import CommunityModule

ext = APIRouter(prefix="/ext/v1", tags=["Extension API v1"])
ext_limiter = RateLimiter(max_requests=240, window_seconds=60)


class Installation:
    def __init__(self, module: CommunityModule):
        self.module = module
        self.scopes = set(module.scopes or [])

    def need(self, scope: str) -> None:
        if scope not in self.scopes:
            raise HTTPException(403, f"This installation wasn't granted the scope {scope}")


async def installation(request: Request, db: AsyncSession = Depends(get_db), _=Depends(ext_limiter)) -> Installation:
    """The installation a token belongs to, with its workspace bound (RLS) for the rest of the request."""
    from app.platform.tenancy.context import bind_tenant
    from app.platform.tenancy.models import Tenant

    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if not token.startswith(service.TOKEN_PREFIX):
        raise HTTPException(401, "Missing or malformed installation token", headers={"WWW-Authenticate": "Bearer"})
    # Finding the installation crosses workspaces; the bypass ends before the workspace is bound,
    # otherwise row-level security wouldn't isolate the rest of this request.
    await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
    row = await db.scalar(select(CommunityModule).where(CommunityModule.api_token_hash == service.token_hash(token),
                                                        CommunityModule.status == "active"))
    tenant = await db.get(Tenant, row.tenant_id) if row else None
    await db.execute(text("SELECT set_config('app.bypass', 'off', true)"))
    if row is None or tenant is None:
        raise HTTPException(401, "Unknown or revoked installation token", headers={"WWW-Authenticate": "Bearer"})
    if tenant.status == "suspended":
        raise HTTPException(403, "The workspace is suspended")
    await bind_tenant(db, tenant.id)
    return Installation(row)


def _page(limit: int, offset: int) -> dict:
    return {"limit": limit, "offset": offset}


async def _list(db: AsyncSession, sql: str, count_sql: str, params: dict) -> dict:
    rows = (await db.execute(text(sql), params)).mappings().all()
    total = await db.scalar(text(count_sql), params)
    return {"items": [_plain(dict(r)) for r in rows], "total": total}


def _plain(row: dict) -> dict:
    from datetime import date, datetime
    from decimal import Decimal

    out = {}
    for k, v in row.items():
        if isinstance(v, uuid.UUID):
            v = str(v)
        elif isinstance(v, (datetime, date)):
            v = v.isoformat()
        elif isinstance(v, Decimal):
            v = str(v)
        out[k] = v
    return out


# ── About the installation ────────────────────────────────────────────────────

@ext.get("/me")
async def me(inst: Installation = Depends(installation), db: AsyncSession = Depends(get_db)):
    """The workspace and installation this token belongs to."""
    from app.platform.tenancy.context import current_tenant_id
    from app.platform.tenancy.models import Tenant

    t = await db.get(Tenant, current_tenant_id.get())
    m = inst.module
    return {"workspace": {"id": str(t.id), "name": t.name}, "module": m.module_id, "version": m.version,
            "scopes": sorted(inst.scopes), "entities": sorted(m.entities or {})}


# ── The module's own records ──────────────────────────────────────────────────

def _entity(inst: Installation, entity: str) -> dict:
    e = (inst.module.entities or {}).get(entity)
    if e is None:
        raise HTTPException(404, f"This module has no entity '{entity}'")
    return e


@ext.get("/records/{entity}")
async def list_records(entity: str, q: str | None = None, page: int = Query(1, ge=1),
                       inst: Installation = Depends(installation), db: AsyncSession = Depends(get_db)):
    return await service.list_records(db, inst.module, _entity(inst, entity), q, page)


@ext.post("/records/{entity}", status_code=201)
async def create_record(entity: str, values: dict[str, Any] = Body(...), inst: Installation = Depends(installation),
                        db: AsyncSession = Depends(get_db)):
    return service.record_out(await service.create_record(db, inst.module, _entity(inst, entity), values, None))


@ext.get("/records/{entity}/{record_id}")
async def get_record(entity: str, record_id: uuid.UUID, inst: Installation = Depends(installation),
                     db: AsyncSession = Depends(get_db)):
    return service.record_out(await service.get_record(db, inst.module, _entity(inst, entity), record_id))


@ext.patch("/records/{entity}/{record_id}")
async def update_record(entity: str, record_id: uuid.UUID, values: dict[str, Any] = Body(...),
                        inst: Installation = Depends(installation), db: AsyncSession = Depends(get_db)):
    e = _entity(inst, entity)
    r = await service.get_record(db, inst.module, e, record_id)
    return service.record_out(await service.update_record(db, inst.module, e, r, values))


@ext.delete("/records/{entity}/{record_id}", status_code=204)
async def delete_record(entity: str, record_id: uuid.UUID, inst: Installation = Depends(installation),
                        db: AsyncSession = Depends(get_db)):
    e = _entity(inst, entity)
    await service.delete_record(db, await service.get_record(db, inst.module, e, record_id))


# ── Built-in data, by scope ───────────────────────────────────────────────────

Limit = Query(50, ge=1, le=200)
Offset = Query(0, ge=0)


@ext.get("/customers")
async def customers(q: str | None = None, limit: int = Limit, offset: int = Offset,
                    inst: Installation = Depends(installation), db: AsyncSession = Depends(get_db)):
    inst.need("customers:read")
    where = "WHERE name ILIKE :q OR phone ILIKE :q" if q else ""
    params = {**_page(limit, offset), "q": f"%{q}%"}
    return await _list(db, f"SELECT id, name, phone, address, balance, credit_limit, created_at FROM customers {where} "  # noqa: S608
                           "ORDER BY created_at DESC LIMIT :limit OFFSET :offset", f"SELECT count(*) FROM customers {where}", params)  # noqa: S608


class NewCustomer(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    phone: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=256)


@ext.post("/customers", status_code=201)
async def create_customer(data: NewCustomer, inst: Installation = Depends(installation), db: AsyncSession = Depends(get_db)):
    inst.need("customers:write")
    from app.modules.general.contacts.models.party import Customer

    c = Customer(name=data.name.strip(), phone=data.phone, address=data.address)
    db.add(c)
    await db.commit()
    return {"id": str(c.id), "name": c.name, "phone": c.phone, "address": c.address}


@ext.get("/suppliers")
async def suppliers(limit: int = Limit, offset: int = Offset, inst: Installation = Depends(installation),
                    db: AsyncSession = Depends(get_db)):
    inst.need("suppliers:read")
    return await _list(db, "SELECT id, name, phone, address, balance, is_active FROM suppliers ORDER BY name LIMIT :limit OFFSET :offset",
                       "SELECT count(*) FROM suppliers", _page(limit, offset))


@ext.get("/products")
async def products(q: str | None = None, limit: int = Limit, offset: int = Offset,
                   inst: Installation = Depends(installation), db: AsyncSession = Depends(get_db)):
    inst.need("products:read")
    where = "WHERE is_active AND (name ILIKE :q OR code ILIKE :q OR barcode = :raw)" if q else "WHERE is_active"
    params = {**_page(limit, offset), "q": f"%{q}%", "raw": q}
    return await _list(db, "SELECT id, code, barcode, name, unit, retail_price, wholesale_price, updated_at "  # noqa: S608
                           f"FROM products {where} ORDER BY name LIMIT :limit OFFSET :offset",
                       f"SELECT count(*) FROM products {where}", params)  # noqa: S608


@ext.get("/stock")
async def stock(product_id: uuid.UUID | None = None, limit: int = Limit, offset: int = Offset,
                inst: Installation = Depends(installation), db: AsyncSession = Depends(get_db)):
    inst.need("stock:read")
    where = "WHERE product_id = :p" if product_id else ""
    params = {**_page(limit, offset), "p": product_id}
    return await _list(db, f"SELECT product_id, warehouse_id AS branch_id, qty, updated_at FROM stock_balances {where} "  # noqa: S608
                           "ORDER BY updated_at DESC LIMIT :limit OFFSET :offset", f"SELECT count(*) FROM stock_balances {where}", params)  # noqa: S608


@ext.get("/sales")
async def sales(since: str | None = None, limit: int = Limit, offset: int = Offset,
                inst: Installation = Depends(installation), db: AsyncSession = Depends(get_db)):
    """Confirmed sales, newest first; `since` (ISO time) for sales after it."""
    inst.need("sales:read")
    where = "WHERE status <> 'draft'" + (" AND created_at > CAST(:since AS timestamptz)" if since else "")
    params = {**_page(limit, offset), "since": since}
    page = await _list(db, "SELECT id, invoice_number, customer_id, warehouse_id AS branch_id, status, total, net_total, "  # noqa: S608
                           f"paid_amount, is_credit, created_at FROM sales {where} ORDER BY created_at DESC LIMIT :limit OFFSET :offset",
                       f"SELECT count(*) FROM sales {where}", params)  # noqa: S608
    ids = [i["id"] for i in page["items"]]
    if ids:
        lines = (await db.execute(text("SELECT sale_id, product_id, qty, unit_price, discount FROM sale_items "
                                       "WHERE sale_id = ANY(CAST(:ids AS uuid[]))"), {"ids": ids})).mappings().all()
        by_sale: dict[str, list] = {}
        for ln in lines:
            item = _plain(dict(ln))
            by_sale.setdefault(item.pop("sale_id"), []).append(item)
        for s in page["items"]:
            s["lines"] = by_sale.get(s["id"], [])
    return page


@ext.get("/employees")
async def employees(limit: int = Limit, offset: int = Offset, inst: Installation = Depends(installation),
                    db: AsyncSession = Depends(get_db)):
    inst.need("employees:read")
    return await _list(db, "SELECT id, emp_code, name, position, is_active FROM hr_employees ORDER BY name LIMIT :limit OFFSET :offset",
                       "SELECT count(*) FROM hr_employees", _page(limit, offset))


@ext.get("/branches")
async def branches(limit: int = Limit, offset: int = Offset, inst: Installation = Depends(installation),
                   db: AsyncSession = Depends(get_db)):
    inst.need("branches:read")
    return await _list(db, "SELECT id, code, name, is_active FROM warehouses ORDER BY name LIMIT :limit OFFSET :offset",
                       "SELECT count(*) FROM warehouses", _page(limit, offset))
