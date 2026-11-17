"""The document archive. Reading it needs `archive` (it holds customers' names and amounts), as
deleting does; filters are typed (an unknown type or a bad date is a 422, never a 500) and dates are
whole days in the workspace's time zone."""
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError, NotFoundError
from app.db.base import get_db
from app.dependencies import require_perm
from app.platform.archive.models import ArchivedDocument, DocType
from app.platform.tenancy import clock

router = APIRouter(prefix="/archive", tags=["archive"])


@router.get("")
async def list_documents(
    doc_type: DocType | None = None,
    search: Annotated[str | None, Query(max_length=128)] = None,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_perm("archive")),
):
    from sqlalchemy import text as sqlt
    if from_date and to_date and from_date > to_date:
        raise BusinessError("تاريخ البداية بعد تاريخ النهاية")
    conditions = ["1=1"]
    params: dict = {"limit": limit}
    if doc_type:
        conditions.append("ad.doc_type = :doc_type")
        params["doc_type"] = doc_type.value
    if search:
        conditions.append("(ad.doc_number ILIKE :search OR ad.customer_name ILIKE :search)")
        params["search"] = f"%{search}%"
    start, end = clock.day_bounds(from_date, to_date)
    if start:
        conditions.append("ad.created_at >= :from_date")
        params["from_date"] = start
    if end:
        conditions.append("ad.created_at < :to_date")
        params["to_date"] = end
    rows = await db.execute(sqlt(f"""
        SELECT ad.*, u.full_name as created_by_name
        FROM archived_documents ad
        LEFT JOIN users u ON u.id = ad.created_by
        WHERE {' AND '.join(conditions)}
        ORDER BY ad.created_at DESC LIMIT :limit
    """), params)
    return [dict(r._mapping) for r in rows.fetchall()]


@router.get("/{doc_id}")
async def get_document(doc_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_perm("archive"))):
    result = await db.execute(select(ArchivedDocument).where(ArchivedDocument.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise NotFoundError()
    return doc


@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_perm("archive"))):
    result = await db.execute(select(ArchivedDocument).where(ArchivedDocument.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise NotFoundError()

    # If this archive row is linked to a real business record, don't hard-delete it.
    # Example: shift handover docs referenced by shifts (ref_id = shift.id).
    if doc.ref_id is not None:
        raise BusinessError(f"لا يمكن حذف مستند مرتبط ({doc.doc_type}) — استخدم إلغاء/تراجع من العملية الأصلية")

    await db.delete(doc)
    await db.commit()
