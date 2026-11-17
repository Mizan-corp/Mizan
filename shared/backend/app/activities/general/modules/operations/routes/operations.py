"""Stock operation documents (archived in archived_documents):
- إذن صرف (dispatch): stock moves from one warehouse to another.
- طلب نواقص (stock_request): a request document; no stock moves.
Goods from a supplier come in through a purchase order (/purchases), never here.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import require_perm
from app.activities.general.modules.operations import service
from app.activities.general.modules.operations.schemas import DispatchRequest, StockRequestRequest
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


@router.post("/goods-receipt", status_code=410)
async def goods_receipt(_: User = Depends(require_perm("operations"))):
    """Removed (OPS-1): it put stock and its cost in with no supplier and no ledger entry."""
    raise HTTPException(410, "استلام البضاعة من مورد يُسجَّل الآن بأمر شراء من شاشة المشتريات "
                             "(المورد، المستحق له، وقيد المخزون في الدفاتر) — هذه العملية لم تعد متاحة هنا")


@router.post("/stock-request")
async def stock_request(data: StockRequestRequest, db: AsyncSession = Depends(get_db),
                        current_user: User = Depends(require_perm("operations"))):
    """طلب نواقص — مستند طلب توريد بدون حركة مخزون فورية."""
    result = await service.request_stock(db, data, current_user)
    await db.commit()
    return result


@router.get("/")
async def list_operations(
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_perm("operations")),
):
    """The operation documents (dispatch, past goods receipts, stock requests), newest first."""
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
