"""Plans, checkout through Paymob, invoices and the Paymob callback."""
from __future__ import annotations

import logging
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plans import PLANS_CONFIG
from app.db.base import get_db
from app.models.billing import BillingInvoice
from app.models.owner import OwnerAccount, PaymentTransaction
from app.models.tenant import PlatformAuditLog, Tenant
from app.integrations.paymob import service as paymob
from app.platform.auth.services.owners import _bearer, bypass_rls, get_current_owner, owned_workspace
from app.platform.billing.services.subscriptions import PAID_PLANS, activate_invoice, new_invoice
from owner_api.common import invoice_out

logger = logging.getLogger("mizan.owner.billing")

router = APIRouter(prefix="/account", tags=["billing"])


async def optional_owner(token: str | None = Depends(_bearer), db: AsyncSession = Depends(get_db)) -> OwnerAccount | None:
    if not token:
        return None
    try:
        return await get_current_owner(token, db)
    except HTTPException:
        return None


@router.get("/plans")
async def plans(owner: OwnerAccount | None = Depends(optional_owner)):
    keys = ("id", "name", "name_en", "price_monthly_egp", "price_annual_egp", "max_users", "max_branches",
            "max_monthly_sales", "popular", "features")
    open_to_owner = paymob.can_pay(owner)
    return {
        "plans": [{k: p.get(k) for k in keys} for pid, p in PLANS_CONFIG.items() if pid in PAID_PLANS],
        "online_payment": open_to_owner,
        # card | wallet (choose in the panel), or "any" (Paymob's page offers every method)
        "payment_methods": paymob.methods() if open_to_owner else [],
        "test_mode": bool(paymob.test_owners()) and open_to_owner,
    }


class CheckoutRequest(BaseModel):
    plan: str
    cycle: Literal["monthly", "annual"] = "monthly"
    method: Literal["card", "wallet"] | None = None
    wallet_number: str | None = None


@router.post("/workspaces/{tenant_id}/checkout")
async def checkout(
    tenant_id: uuid.UUID,
    data: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    owner: OwnerAccount = Depends(get_current_owner),
):
    """Create an invoice and a Paymob checkout for it; the panel sends the owner there."""
    if data.plan not in PAID_PLANS:
        raise HTTPException(status_code=422, detail="باقة غير معروفة")
    if not paymob.can_pay(owner):
        raise HTTPException(status_code=503, detail="الدفع الإلكتروني غير متاح الآن. تواصل معنا لإتمام الاشتراك.")
    available = paymob.methods()
    if available != ["any"]:
        if data.method not in available:
            raise HTTPException(status_code=422, detail="اختر طريقة الدفع: بطاقة أو محفظة إلكترونية.")
        if data.method == "wallet" and not paymob.normalize_wallet(data.wallet_number or ""):
            raise HTTPException(status_code=422, detail="اكتب رقم المحفظة الإلكترونية (11 رقمًا يبدأ بـ 01).")
    t = await owned_workspace(db, owner, tenant_id)
    if t.status == "suspended":
        raise HTTPException(status_code=403, detail="مساحة العمل هذه موقوفة. تواصل مع الدعم أولًا.")

    # An owner who starts again abandons the previous checkout.
    await db.execute(
        update(BillingInvoice)
        .where(BillingInvoice.tenant_id == t.id, BillingInvoice.status == "pending", BillingInvoice.payment_method == "paymob")
        .values(status="cancelled")
    )
    invoice = await new_invoice(db, t, plan=data.plan, cycle=data.cycle, method="paymob")
    try:
        session = await paymob.create_checkout(invoice, t, owner, method=data.method, wallet_number=data.wallet_number)
    except paymob.PaymobError as e:
        await db.rollback()
        logger.warning("Checkout failed for %s: %s", t.id, e)
        raise HTTPException(status_code=502, detail="تعذر فتح صفحة الدفع الآن. حاول مرة أخرى بعد قليل.") from None
    if session.get("order_id"):
        invoice.payment_gateway_ref = f"paymob-order:{session['order_id']}"
    await db.commit()
    return {"invoice": invoice_out(invoice, t), "checkout_url": session["checkout_url"]}


@router.get("/invoices")
async def invoices(db: AsyncSession = Depends(get_db), owner: OwnerAccount = Depends(get_current_owner)):
    tenants = {t.id: t for t in (await db.execute(select(Tenant).where(Tenant.owner_account_id == owner.id))).scalars()}
    if not tenants:
        return {"items": []}
    rows = (await db.execute(
        select(BillingInvoice)
        .where(BillingInvoice.tenant_id.in_(tenants), BillingInvoice.status != "cancelled")
        .order_by(BillingInvoice.created_at.desc()).limit(200)
    )).scalars().all()
    return {"items": [invoice_out(i, tenants.get(i.tenant_id)) for i in rows]}


@router.get("/invoices/{ref}")
async def invoice(ref: str, db: AsyncSession = Depends(get_db), owner: OwnerAccount = Depends(get_current_owner)):
    row = (await db.execute(
        select(BillingInvoice, Tenant).join(Tenant, Tenant.id == BillingInvoice.tenant_id)
        .where(BillingInvoice.invoice_ref == ref, Tenant.owner_account_id == owner.id)
    )).first()
    if not row:
        raise HTTPException(status_code=404, detail="الفاتورة غير موجودة")
    return invoice_out(row[0], row[1])


# ─── Paymob callback ───────────────────────────────────────────────────────


async def _invoice_for(db: AsyncSession, obj: dict) -> BillingInvoice | None:
    order = obj.get("order") or {}
    refs = [order.get("merchant_order_id"), obj.get("special_reference"),
            ((obj.get("payment_key_claims") or {}).get("extra") or {}).get("invoice_ref")]
    for ref in filter(None, refs):
        inv = await db.scalar(select(BillingInvoice).where(BillingInvoice.invoice_ref == str(ref)))
        if inv:
            return inv
    if order.get("id"):
        return await db.scalar(select(BillingInvoice).where(BillingInvoice.payment_gateway_ref == f"paymob-order:{order['id']}"))
    return None


@router.post("/paymob/callback")
async def paymob_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """Paymob's transaction-processed callback. Verified by HMAC, applied once."""
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid body") from None
    if body.get("type") not in (None, "TRANSACTION"):
        return {"ok": True, "ignored": body.get("type")}
    obj = body.get("obj") or {}
    if not paymob.verify_hmac(obj, request.query_params.get("hmac")):
        logger.warning("Paymob callback with a bad HMAC (txn %s)", obj.get("id"))
        raise HTTPException(status_code=403, detail="Invalid signature")

    await bypass_rls(db)
    state = paymob.transaction_state(obj)
    inv = await _invoice_for(db, obj)
    amount_cents = int(obj.get("amount_cents") or 0)
    stored = await db.scalar(
        insert(PaymentTransaction)
        .values(
            id=uuid.uuid4(), provider="paymob", event_key=f"paymob:{obj.get('id')}:{state}",
            provider_txn_id=str(obj.get("id")), invoice_id=inv.id if inv else None, state=state,
            amount_cents=amount_cents, currency=str(obj.get("currency") or ""), raw=obj,
        )
        .on_conflict_do_nothing(index_elements=["event_key"])
        .returning(PaymentTransaction.id)
    )
    if stored is None:
        return {"ok": True, "duplicate": True}
    if inv is None:
        logger.warning("Paymob txn %s matches no invoice", obj.get("id"))
        await db.commit()
        return {"ok": True, "matched": False}

    action = None
    if state == "paid":
        expected = round(inv.amount_egp * 100)
        if amount_cents != expected or (obj.get("currency") or "EGP") != "EGP":
            logger.error("Paymob txn %s amount %s %s ≠ invoice %s (%s)", obj.get("id"), amount_cents,
                         obj.get("currency"), inv.invoice_ref, expected)
            inv.notes = f"{inv.notes or ''}\nPaymob txn {obj.get('id')} paid {amount_cents / 100} {obj.get('currency')}, expected {expected / 100}".strip()
        elif inv.status != "paid":
            # A late payment on an abandoned checkout still counts.
            await activate_invoice(db, inv, reference=f"paymob:{obj.get('id')}")
            action = "invoice_paid_online"
    elif state in ("refunded", "voided") and inv.status == "paid":
        inv.status = "refunded"
        action = "invoice_refunded_online"

    if action:
        tenant_name = await db.scalar(select(Tenant.name).where(Tenant.id == inv.tenant_id))
        db.add(PlatformAuditLog(
            tenant_id=inv.tenant_id, action=action,
            details={"invoice": inv.invoice_ref, "amount_egp": inv.amount_egp, "plan": inv.plan,
                     "transaction": str(obj.get("id")), "workspace_name": tenant_name},
        ))
    await db.commit()
    return {"ok": True, "state": state}
