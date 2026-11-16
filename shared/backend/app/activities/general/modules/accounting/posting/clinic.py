"""Posting rules for clinic invoices (ADR-014 D3, step 3). A clinic invoice is one sale made at its
first payment, with one payment line per payment; the event 'clinic.invoice_paid' carries the
invoice and the payment just recorded.

Invoice revenue (source 'clinic_invoice', id: the invoice, event 'revenue'), posted once, at the first
payment the ledger sees (later payments find it posted):
    Dr receivables (the patient's share not yet paid)      }  no party: patients are not customers
    Dr insurance receivables (the insurer's share)         }
    Cr sales (revenue: the patient's share + the insurer's share)
Each payment (source 'clinic_payment', id: the sale_payments row, event 'confirm'):
    Dr the money account (cash: the drawer of the branch of the cashier's open shift, as at the POS;
       bank, card, wallet and the like: the default bank) / Cr receivables
Payments made before the ledger started are not part of the revenue entry (it takes what was unpaid).
Insurance claim approval and payment are not posted yet.
"""
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.accounting.posting.common import payment_account, role, shift_warehouse, tenant_of
from app.activities.general.modules.accounting.services.posting import cr, dr, post, today


async def on_clinic_invoice_paid(db: AsyncSession, *, invoice: dict, payment: dict, user_id=None, **_) -> None:
    tid = tenant_of(invoice)
    wh = invoice.get("warehouse_id")
    receivables = await role(db, tid, "receivables")
    unpaid = max(Decimal("0"), invoice["patient_amount"] - invoice["paid_before"])
    insurance = invoice["insurance_amount"]
    revenue = unpaid + insurance
    if revenue > 0:
        lines = [dr(receivables, unpaid), cr(await role(db, tid, "sales"), revenue)]
        if insurance > 0:
            lines.insert(1, dr(await role(db, tid, "insurance_receivables"), insurance))
        await post(db, tid, "clinic_invoice", invoice["id"], "revenue", today(), lines,
                   memo=f"فاتورة عيادة {invoice['invoice_ref']} — {invoice['patient_name']}", warehouse_id=wh,
                   user_id=user_id)
    amount = Decimal(str(payment["amount"] or 0))
    if amount <= 0:
        return
    drawer_wh = await shift_warehouse(db, payment.get("shift_id")) or wh
    money = await payment_account(db, tid, payment["method"], drawer_warehouse=drawer_wh)
    await post(db, tid, "clinic_payment", payment["id"], "confirm", today(),
               [dr(money, amount, warehouse_id=wh), cr(receivables, amount, warehouse_id=wh)],
               memo=f"سداد فاتورة عيادة {invoice['invoice_ref']}", warehouse_id=wh, user_id=user_id)
