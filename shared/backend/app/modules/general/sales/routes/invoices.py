"""
Invoices API Router:
Branded PDF generation (GET /invoices/{id}/pdf) and Email Delivery (POST /invoices/{id}/send).
"""
import uuid

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import get_current_user, require_perm
from app.modules.general.sales.services import invoices as invoices_service
from app.platform.auth.models.user import User

router = APIRouter(prefix="/invoices", tags=["invoices"])


class SendInvoiceEmailIn(BaseModel):
    email: str | None = None
    subject: str | None = None


@router.get("/{invoice_id}/pdf")
async def get_invoice_pdf(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate and return styled branded PDF for an invoice."""
    pdf_bytes, sale = await invoices_service.render_pdf(db, invoice_id, current_user.tenant_id)
    inv_num = sale.get("invoice_number", str(invoice_id))
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="invoice-{inv_num}.pdf"'})


@router.post("/{invoice_id}/send")
async def send_invoice_email(
    invoice_id: uuid.UUID,
    data: SendInvoiceEmailIn = SendInvoiceEmailIn(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm("sales")),
):
    """Send branded invoice PDF to customer via email."""
    result = await invoices_service.email_invoice(db, invoice_id, data.email, data.subject, current_user)
    await db.commit()
    return result
