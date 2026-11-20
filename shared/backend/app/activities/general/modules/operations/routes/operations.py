"""Stock operation documents (archived in archived_documents):
- إذن صرف (dispatch): stock moves from one warehouse to another; cancelling moves it back.
- طلب نواقص (stock_request): a request document; no stock moves.
Goods from a supplier come in through a purchase order (/purchases), never here.

A retried dispatch or request (a double click, a lost answer) names its attempt with an
`Idempotency-Key` header or a `client_id` in the body and gets the first answer back (OPS-5).
"""
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import require_perm
from app.framework import idempotency
from app.activities.general.modules.operations import service
from app.activities.general.modules.operations.schemas import DispatchRequest, StockRequestRequest
from app.platform.archive.models import DocType
from app.platform.auth.models.user import User

router = APIRouter(prefix="/operations", tags=["operations"])


class CancelRequest(BaseModel):
    reason: str | None = Field(None, max_length=500)


async def _once(db: AsyncSession, scope: str, key_header: str | None, data, user: User, work) -> dict:
    key = idempotency.key_of(key_header, data.client_id)
    replay = await idempotency.claim(db, scope, key, data.model_dump(mode="json"), user.id)
    if replay is not None:
        return replay
    result = await work()
    await idempotency.remember(db, scope, key, result)
    await db.commit()
    return result


@router.post("/dispatch")
async def dispatch_order(data: DispatchRequest, db: AsyncSession = Depends(get_db),
                         current_user: User = Depends(require_perm("operations")),
                         idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    """إذن صرف — نقل بضاعة من مخزن إلى معرض."""
    return await _once(db, "operations.dispatch", idempotency_key, data, current_user,
                       lambda: service.dispatch(db, data, current_user))


@router.post("/goods-receipt", status_code=410)
async def goods_receipt(_: User = Depends(require_perm("operations"))):
    """Removed (OPS-1): it put stock and its cost in with no supplier and no ledger entry."""
    raise HTTPException(410, "استلام البضاعة من مورد يُسجَّل الآن بأمر شراء من شاشة المشتريات "
                             "(المورد، المستحق له، وقيد المخزون في الدفاتر) — هذه العملية لم تعد متاحة هنا")


@router.post("/stock-request")
async def stock_request(data: StockRequestRequest, db: AsyncSession = Depends(get_db),
                        current_user: User = Depends(require_perm("operations")),
                        idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    """طلب نواقص — مستند طلب توريد بدون حركة مخزون فورية."""
    return await _once(db, "operations.stock_request", idempotency_key, data, current_user,
                       lambda: service.request_stock(db, data, current_user))


@router.post("/{doc_id}/cancel")
async def cancel_dispatch(doc_id: uuid.UUID, data: CancelRequest | None = None, db: AsyncSession = Depends(get_db),
                          current_user: User = Depends(require_perm("operations:cancel"))):
    """إلغاء إذن صرف — تعود البضاعة إلى مخزن المصدر (managers: `operations:cancel`)."""
    result = await service.cancel_dispatch(db, doc_id, current_user, data.reason if data else None)
    await db.commit()
    return result


@router.get("/")
async def list_operations(
    doc_type: Literal["dispatch_order", "goods_receipt", "stock_request"] | None = None,
    page: int = Query(1, ge=1, le=100000),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_perm("operations")),
):
    """The operation documents (dispatch, past goods receipts, stock requests), newest first:
    {items, total, page, pages}."""
    return await service.list_documents(db, DocType(doc_type) if doc_type else None, page, page_size)
