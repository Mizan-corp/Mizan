import uuid

from fastapi import Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import get_print_user
from app.platform.auth.models.user import User

from . import _make_pdf, PaperSize, router


async def _inventory_html(db: AsyncSession, warehouse_id: uuid.UUID, user: User) -> str:
    """The branch's stock sheet, the same document as /reports/inventory/print: `inventory` or
    `reports`, a branch the user reaches (404 for an unknown one, or another workspace's), costs only
    with `reports:finance`."""
    from fastapi import HTTPException

    from app.activities.general.modules.reporting import service as report_service
    from app.activities.general.modules.reporting.printing import inventory_html
    from app.activities.general.modules.reporting.scope import FINANCE, branch_scope
    from app.platform.permissions.access import can

    if not can(user, "inventory", "reports"):
        raise HTTPException(403, "ليس لديك صلاحية طباعة تقرير المخزون")
    await branch_scope(db, user, warehouse_id)
    data = await report_service.inventory_print_report(db, warehouse_id, with_cost=can(user, FINANCE))
    return inventory_html(data)


@router.get("/inventory/{warehouse_id}", response_class=HTMLResponse)
async def print_inventory(warehouse_id: uuid.UUID,
                          db: AsyncSession = Depends(get_db), user: User = Depends(get_print_user)):
    return HTMLResponse(await _inventory_html(db, warehouse_id, user))


@router.get("/pdf/inventory/{warehouse_id}")
async def pdf_inventory(warehouse_id: uuid.UUID, paper_size: PaperSize = None,
                        db: AsyncSession = Depends(get_db), user: User = Depends(get_print_user)):
    html_resp = HTMLResponse(await _inventory_html(db, warehouse_id, user))
    return await _make_pdf(html_resp, "تقرير المخزون", f"inventory_{warehouse_id}.pdf", db, paper_size)
