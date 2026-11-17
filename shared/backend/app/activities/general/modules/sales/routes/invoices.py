"""
Invoices API Router:
Branded PDF generation (GET /invoices/{id}/pdf) and Email Delivery (POST /invoices/{id}/send).
"""
import uuid

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratelimit import RateLimiter
from app.db.base import get_db
from app.dependencies import require_perm
from app.activities.general.modules.sales.routes.sales import _sale_in_reach
from app.activities.general.modules.sales.services import invoices as invoices_service
from app.platform.auth.models.user import User

router = APIRouter(prefix="/invoices", tags=["invoices"])

# Sending an invoice by email goes through the platform's mail provider (SAL-12): a few a minute
# per user, and a ceiling per workspace, so a script can't send mail in the workspace's name.
email_user_limiter = RateLimiter(max_requests=10, window_seconds=600)
email_workspace_limiter = RateLimiter(max_requests=100, window_seconds=3600)


class SendInvoiceEmailIn(BaseModel):
    email: str | None = Field(None, max_length=254)
    subject: str | None = Field(None, max_length=200)


@router.get("/{invoice_id}/pdf")
async def get_invoice_pdf(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm("sales", "pos")),
):
    """The invoice as a branded PDF (or a printable page where the server can't render PDFs), for
    a sale in a branch the user reaches."""
    await _sale_in_reach(db, invoice_id, current_user)
    content, media, ext, sale = await invoices_service.render_file(db, invoice_id, current_user.tenant_id)
    inv_num = sale.get("invoice_number", str(invoice_id))
    return Response(content=content, media_type=media,
                    headers={"Content-Disposition": f'inline; filename="invoice-{inv_num}.{ext}"'})


@router.post("/{invoice_id}/send")
async def send_invoice_email(
    invoice_id: uuid.UUID,
    data: SendInvoiceEmailIn = SendInvoiceEmailIn(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm("sales")),
):
    """Send branded invoice PDF to customer via email."""
    await email_user_limiter.hit(f"invoice-email:user:{current_user.id}")
    await email_workspace_limiter.hit(f"invoice-email:ws:{current_user.tenant_id}")
    await _sale_in_reach(db, invoice_id, current_user)
    result = await invoices_service.email_invoice(db, invoice_id, data.email, data.subject, current_user)
    await db.commit()
    return result
