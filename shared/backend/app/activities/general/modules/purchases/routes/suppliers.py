import json
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page
from app.dependencies import get_current_user, get_db, require_perm

router = APIRouter(prefix="/suppliers", tags=["suppliers"])

class SupplierIn(BaseModel):
    name: str
    phone: str | None = None
    address: str | None = None
    type: str = "supplier"
    notes: str | None = None
    extra: dict | None = None  # custom fields (app/framework/fields.py)

class TxIn(BaseModel):
    amount: Decimal = Field(..., gt=0)
    type: str  # debit (an amount we owe) / credit (a payment to the supplier)
    reference_doc: str | None = None
    notes: str | None = None
    # A payment (credit) says where the money came from: a safe (or bank account) or a wallet.
    method: str | None = Field(None, max_length=32)
    safe_id: uuid.UUID | None = None
    wallet_id: uuid.UUID | None = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v):
        if v not in ("debit", "credit"):
            raise ValueError("type must be 'debit' or 'credit'")
        return v

async def _clean_extra(db: AsyncSession, extra: dict | None, current: dict | None = None, partial: bool = False) -> dict:
    """A supplier's custom field values, checked against the workspace's fields."""
    from app.framework.fields import clean_extra
    from app.framework.hooks import workspace_activity

    return await clean_extra(db, "supplier", extra, await workspace_activity(db), current=current, partial=partial)


@router.get("")
async def list_suppliers(type: str | None = None, include_inactive: bool = False, page: int = 1, page_size: int = 200, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    where = "WHERE true" if include_inactive else "WHERE is_active=true"
    params = {}
    if type:
        where += " AND type=:type"
        params["type"] = type
    total = (await db.execute(text(f"SELECT COUNT(*) FROM suppliers {where}"), params)).scalar()
    r = await db.execute(text(f"SELECT * FROM suppliers {where} ORDER BY name OFFSET :offset LIMIT :limit"), {**params, "offset": (page - 1) * page_size, "limit": page_size})
    items = [dict(row._mapping) for row in r.fetchall()]
    return Page(items=items, total=total, page=page, size=page_size, pages=-( -total // page_size))

@router.post("", status_code=201)
async def create_supplier(data: SupplierIn, db: AsyncSession = Depends(get_db), _=Depends(require_perm("inventory", "purchases"))):
    payload = data.model_dump()
    payload["extra"] = json.dumps(await _clean_extra(db, payload.get("extra")))
    r = await db.execute(text(
        "INSERT INTO suppliers (id,name,phone,address,type,notes,balance,extra) VALUES (gen_random_uuid(),:name,:phone,:address,:type,:notes,0,CAST(:extra AS jsonb)) RETURNING id,name,phone,address,type,balance,notes,extra,created_at"
    ), payload)
    await db.commit()
    return dict(r.fetchone()._mapping)

@router.put("/{sid}")
async def update_supplier(sid: uuid.UUID, data: SupplierIn, db: AsyncSession = Depends(get_db), _=Depends(require_perm("inventory", "purchases"))):
    payload = data.model_dump()
    current = await db.scalar(text("SELECT extra FROM suppliers WHERE id=:id"), {"id": sid})
    payload["extra"] = json.dumps(await _clean_extra(db, payload.get("extra"), current=current or {}, partial=data.extra is None))
    r = await db.execute(text(
        "UPDATE suppliers SET name=:name,phone=:phone,address=:address,type=:type,notes=:notes,extra=CAST(:extra AS jsonb) WHERE id=:id RETURNING *"
    ), {**payload, "id": sid})
    await db.commit()
    row = r.fetchone()
    if not row:
        raise HTTPException(404)
    return dict(row._mapping)

@router.delete("/{sid}", status_code=204)
async def delete_supplier(sid: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_perm("inventory"))):
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
        raise HTTPException(404, "المورد غير موجود")
    await db.commit()


@router.post("/{sid}/deactivate")
async def deactivate_supplier(sid: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_perm("inventory", "purchases"))):
    return await _set_active(db, sid, False)


@router.post("/{sid}/activate")
async def activate_supplier(sid: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_perm("inventory", "purchases"))):
    return await _set_active(db, sid, True)


async def _set_active(db: AsyncSession, sid: uuid.UUID, active: bool) -> dict:
    r = await db.execute(text("UPDATE suppliers SET is_active=:a WHERE id=:id"), {"a": active, "id": sid})
    if r.rowcount == 0:
        raise HTTPException(404, "المورد غير موجود")
    await db.commit()
    return {"id": str(sid), "is_active": active}


@router.get("/{sid}/ledger")
async def supplier_ledger(sid: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    sup = await db.execute(text("SELECT * FROM suppliers WHERE id=:id"), {"id": sid})
    sup_row = sup.fetchone()
    if not sup_row:
        raise HTTPException(404)
    txs = await db.execute(text(
        "SELECT st.*, sf.name AS safe_name, pw.name AS wallet_name FROM supplier_transactions st "
        "LEFT JOIN safes sf ON sf.id = st.safe_id LEFT JOIN payment_wallets pw ON pw.id = st.wallet_id "
        "WHERE st.supplier_id=:id ORDER BY st.created_at DESC"
    ), {"id": sid})
    return {
        "supplier": dict(sup_row._mapping),
        "transactions": [dict(r._mapping) for r in txs.fetchall()]
    }

@router.post("/{sid}/transactions", status_code=201)
async def add_transaction(sid: uuid.UUID, data: TxIn, db: AsyncSession = Depends(get_db), current_user=Depends(require_perm("inventory", "purchases"))):
    """debit = an amount we owe (+), credit = a payment to the supplier (−) from a safe or wallet."""
    from app.activities.general.modules.purchases.service import record_supplier_transaction

    row = await record_supplier_transaction(db, sid, data.amount, data.type, current_user, reference_doc=data.reference_doc,
                                            notes=data.notes, method=data.method, safe_id=data.safe_id, wallet_id=data.wallet_id)
    await db.commit()
    return {"ok": True, "id": str(row["id"])}
