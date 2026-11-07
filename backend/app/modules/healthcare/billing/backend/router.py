from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.base import get_db
from app.dependencies import get_current_user
from .models import PatientInvoice
from .schemas import InvoiceCreate, InvoiceResponse

router = APIRouter(prefix="/healthcare/billing", tags=["Healthcare - Billing (HLT-15)"])

@router.get("/invoices", response_model=List[InvoiceResponse])
async def list_invoices(patient_id: int | None = None, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(PatientInvoice)
    if patient_id:
        stmt = stmt.where(PatientInvoice.patient_id == patient_id)
    stmt = stmt.order_by(PatientInvoice.id.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/invoices", response_model=InvoiceResponse)
async def create_invoice(data: InvoiceCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    inv = PatientInvoice(**data.model_dump())
    db.add(inv)
    await db.commit()
    await db.refresh(inv)
    return inv

@router.post("/invoices/{id}/pay")
async def pay_invoice(id: int, amount: float, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    inv = await db.get(PatientInvoice, id)
    if not inv:
        raise HTTPException(status_code=404, detail="الفاتورة غير موجودة")
    inv.paid_amount = float(inv.paid_amount or 0) + amount
    if float(inv.paid_amount) >= float(inv.patient_share):
        inv.payment_status = "paid"
    else:
        inv.payment_status = "partially_paid"
    await db.commit()
    return {"id": id, "paid_amount": float(inv.paid_amount), "status": inv.payment_status}
