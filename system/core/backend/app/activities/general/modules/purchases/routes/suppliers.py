import json
import uuid
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page
from app.dependencies import get_db, require_perm

router = APIRouter(prefix="/suppliers", tags=["suppliers"])

SUPPLIER_NOT_FOUND = "المورد غير موجود"

# What the party is to the workspace: a supplier of goods, the manufacturer itself, a distributor or a
# provider of services (rent, maintenance…).
SupplierType = Literal["supplier", "manufacturer", "distributor", "service"]


class SupplierIn(BaseModel):
    model_config = {"str_strip_whitespace": True}
    name: str = Field(..., min_length=1, max_length=128)
    phone: str | None = Field(None, max_length=32)
    address: str | None = Field(None, max_length=500)
    type: SupplierType = "supplier"
    notes: str | None = Field(None, max_length=2000)
    extra: dict | None = None  # custom fields (app/framework/fields.py)

class TxIn(BaseModel):
    amount: Decimal = Field(..., gt=0, le=Decimal("999999999999"))
    type: str  # debit (an amount we owe) / credit (a payment to the supplier)
    reference_doc: str | None = Field(None, max_length=128)
    notes: str | None = Field(None, max_length=1000)
    # A payment (credit) says where the money came from: a safe (or bank account) or a wallet.
    method: str | None = Field(None, max_length=32)
    safe_id: uuid.UUID | None = None
    wallet_id: uuid.UUID | None = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v):
        if v not in ("debit", "credit"):
            raise ValueError("نوع الحركة يجب أن يكون debit (مستحق للمورد) أو credit (دفعة له)")
        return v

async def _clean_extra(db: AsyncSession, extra: dict | None, current: dict | None = None, partial: bool = False) -> dict:
    """A supplier's custom field values, checked against the workspace's fields."""
    from app.framework.fields import clean_extra
    from app.framework.hooks import workspace_activity

    return await clean_extra(db, "supplier", extra, await workspace_activity(db), current=current, partial=partial)


@router.get("")
async def list_suppliers(type: SupplierType | None = None, include_inactive: bool = False,
                         search: str | None = Query(None, max_length=128),
                         page: int = Query(1, ge=1), page_size: int = Query(200, ge=1, le=1000),
                         db: AsyncSession = Depends(get_db), _=Depends(require_perm("purchases", "finance", "accounting:view"))):
    """Suppliers with their balances: for purchasing, finance and the ledger's party picker (which
    loads up to 1,000). `search`: part of the name or the phone."""
    where = "WHERE true" if include_inactive else "WHERE is_active=true"
    params = {}
    if type:
        where += " AND type=:type"
        params["type"] = type
    if search and search.strip():
        where += " AND (name ILIKE :q OR phone ILIKE :q)"
        params["q"] = f"%{search.strip()}%"
    total = (await db.execute(text(f"SELECT COUNT(*) FROM suppliers {where}"), params)).scalar()
    r = await db.execute(text(f"SELECT * FROM suppliers {where} ORDER BY name OFFSET :offset LIMIT :limit"), {**params, "offset": (page - 1) * page_size, "limit": page_size})
    items = [dict(row._mapping) for row in r.fetchall()]
    return Page(items=items, total=total, page=page, size=page_size, pages=-( -total // page_size))

@router.post("", status_code=201)
async def create_supplier(data: SupplierIn, db: AsyncSession = Depends(get_db), _=Depends(require_perm("purchases"))):
    payload = data.model_dump()
    payload["extra"] = json.dumps(await _clean_extra(db, payload.get("extra")))
    r = await db.execute(text(
        "INSERT INTO suppliers (id,name,phone,address,type,notes,balance,extra) VALUES (gen_random_uuid(),:name,:phone,:address,:type,:notes,0,CAST(:extra AS jsonb)) RETURNING id,name,phone,address,type,balance,notes,extra,created_at"
    ), payload)
    await db.commit()
    return dict(r.fetchone()._mapping)

@router.put("/{sid}")
async def update_supplier(sid: uuid.UUID, data: SupplierIn, db: AsyncSession = Depends(get_db), _=Depends(require_perm("purchases"))):
    payload = data.model_dump()
    current = await db.scalar(text("SELECT extra FROM suppliers WHERE id=:id"), {"id": sid})
    payload["extra"] = json.dumps(await _clean_extra(db, payload.get("extra"), current=current or {}, partial=data.extra is None))
    r = await db.execute(text(
        "UPDATE suppliers SET name=:name,phone=:phone,address=:address,type=:type,notes=:notes,extra=CAST(:extra AS jsonb) WHERE id=:id RETURNING *"
    ), {**payload, "id": sid})
    await db.commit()
    row = r.fetchone()
    if not row:
        raise HTTPException(404, SUPPLIER_NOT_FOUND)
    return dict(row._mapping)

@router.delete("/{sid}", status_code=204)
async def delete_supplier(sid: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_perm("purchases"))):
    """A supplier with purchases or account movements is never deleted (ADR-014 D4): deactivate it."""
    used = await db.scalar(text("""
        SELECT EXISTS (SELECT 1 FROM purchase_orders WHERE supplier_id = :id)
            OR EXISTS (SELECT 1 FROM supplier_transactions WHERE supplier_id = :id)
    """), {"id": sid})
    if used:
        raise HTTPException(409, "لا يمكن حذف مورد له مشتريات أو حركات حساب. يمكنك إيقافه بدلًا من ذلك")
    # Soft-delete, as before: supplier prices and history may still refer to it.
    r = await db.execute(text("UPDATE suppliers SET is_active=false WHERE id=:id"), {"id": sid})
    if r.rowcount == 0:
        raise HTTPException(404, SUPPLIER_NOT_FOUND)
    await db.commit()


@router.post("/{sid}/deactivate")
async def deactivate_supplier(sid: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_perm("purchases"))):
    return await _set_active(db, sid, False)


@router.post("/{sid}/activate")
async def activate_supplier(sid: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_perm("purchases"))):
    return await _set_active(db, sid, True)


async def _set_active(db: AsyncSession, sid: uuid.UUID, active: bool) -> dict:
    r = await db.execute(text("UPDATE suppliers SET is_active=:a WHERE id=:id"), {"a": active, "id": sid})
    if r.rowcount == 0:
        raise HTTPException(404, SUPPLIER_NOT_FOUND)
    await db.commit()
    return {"id": str(sid), "is_active": active}


@router.get("/{sid}/ledger")
async def supplier_ledger(sid: uuid.UUID, page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=500),
                          newest_first: bool = False, db: AsyncSession = Depends(get_db),
                          _=Depends(require_perm("purchases", "finance"))):
    """The supplier's account: invoices, payments, returns and charges in date order, with what we owe
    after each line (over the whole account, so every page is right); {supplier, items, total, pages}."""
    from app.activities.general.modules.purchases.service import supplier_statement

    return await supplier_statement(db, sid, page, page_size, newest_first)


@router.post("/{sid}/transactions", status_code=201)
async def add_transaction(sid: uuid.UUID, data: TxIn, db: AsyncSession = Depends(get_db), current_user=Depends(require_perm("finance"))):
    """debit = an amount we owe (+), credit = a payment to the supplier (−) from a safe or wallet.
    Both move money or what we owe and post to the ledger, so they need `finance` (PUR-1)."""
    from app.activities.general.modules.purchases.service import record_supplier_transaction

    row = await record_supplier_transaction(db, sid, data.amount, data.type, current_user, reference_doc=data.reference_doc,
                                            notes=data.notes, method=data.method, safe_id=data.safe_id, wallet_id=data.wallet_id)
    await db.commit()
    return {"ok": True, "id": str(row["id"])}
