"""
operations.py — مستندات العمليات
- إذن صرف (dispatch): من مخزن → معرض
- استلام بضاعة (goods_receipt): من تاجر → مخزن
- طلب نواقص (stock_request): طلب توريد من مخزن
كل عملية تُسجَّل في stock_movements وتُحفَظ في archived_documents تلقائياً.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import get_current_user, require_perm
from app.modules.general.operations import service
from app.modules.general.operations.schemas import DispatchRequest, GoodsReceiptRequest, StockRequestRequest
from app.platform.archive.models import ArchivedDocument, DocType
from app.platform.auth.models.user import User

router = APIRouter(prefix="/operations", tags=["operations"])


@router.post("/dispatch")
async def dispatch_order(data: DispatchRequest, db: AsyncSession = Depends(get_db),
                         current_user: User = Depends(require_perm("operations"))):
    """إذن صرف — نقل بضاعة من مخزن إلى معرض."""
    result = await service.dispatch(db, data, current_user)
    await db.commit()
    return result


@router.post("/goods-receipt")
async def goods_receipt(data: GoodsReceiptRequest, db: AsyncSession = Depends(get_db),
                        current_user: User = Depends(require_perm("operations"))):
    """استلام بضاعة من تاجر — يُضاف للمخزن بأسعار التكلفة."""
    result = await service.receive_goods(db, data, current_user)
    await db.commit()
    return result


@router.post("/stock-request")
async def stock_request(data: StockRequestRequest, db: AsyncSession = Depends(get_db),
                        current_user: User = Depends(require_perm("operations"))):
    """طلب نواقص — مستند طلب توريد بدون حركة مخزون فورية."""
    result = await service.request_stock(db, data, current_user)
    await db.commit()
    return result


@router.get("/")
async def list_operations(
    limit: int = Query(200, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """قائمة بكل مستندات العمليات."""
    # Basic pagination: allow callers to page through archived documents

    result = await db.execute(
        select(ArchivedDocument)
        .where(ArchivedDocument.doc_type.in_([
            DocType.dispatch_order, DocType.goods_receipt, DocType.stock_request
        ]))
        .order_by(ArchivedDocument.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    docs = result.scalars().all()
    return [{"id": str(d.id), "doc_number": d.doc_number, "doc_type": d.doc_type,
             "amount": float(d.amount or 0), "metadata": d.metadata_,
             "created_at": d.created_at.isoformat()} for d in docs]
# Pagination implemented above
