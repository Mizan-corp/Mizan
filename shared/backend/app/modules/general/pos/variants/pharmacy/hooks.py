"""POS, pharmacy variant: dispensing is a sale (uses `pharmacy` and `batches`).

before_confirm: a sale with a prescription-only drug needs the prescriber and the patient; a
controlled drug also needs the patient's national ID and the prescriber's licence.
after_confirm: the prescription is recorded against the sale (numbered if it had no number), and
each controlled line goes into the controlled-drug log with the batches it came from.
Batches themselves (first expiry first out) come from the inventory pharmacy variant.
"""
import uuid
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select

from app.framework import variants

NEEDS_RX = ("doctor_name", "patient_name")
NEEDS_CONTROLLED = ("patient_national_id", "doctor_license")
LABELS = {"doctor_name": "الطبيب المعالج", "patient_name": "اسم المريض",
          "patient_national_id": "الرقم القومي للمريض", "doctor_license": "رقم ترخيص الطبيب"}


async def _drugs(db, lines) -> dict:
    from app.modules.general.inventory.models.product import Product

    ids = {line.product_id for line in lines}
    rows = (await db.execute(select(Product.id, Product.name, Product.extra).where(Product.id.in_(ids)))).all()
    return {r.id: (r.name, r.extra or {}) for r in rows}


async def before_confirm(db, activity_id=None, sale=None, lines=(), **_):
    if not variants.setting("pos", "prescription_check", activity_id, True):
        return None
    drugs = await _drugs(db, lines)
    rx = [name for name, extra in drugs.values() if extra.get("requires_prescription") or extra.get("is_controlled")]
    if not rx:
        return None
    controlled = [name for name, extra in drugs.values() if extra.get("is_controlled")]
    given = sale.extra or {}
    needed = NEEDS_RX + (NEEDS_CONTROLLED if controlled else ())
    missing = [LABELS[k] for k in needed if not str(given.get(k) or "").strip()]
    if missing:
        what = "أدوية مراقبة" if controlled else "أدوية تُصرف بروشتة"
        raise HTTPException(422, f"الفاتورة فيها {what} ({'، '.join(controlled or rx)}): أدخل {'، '.join(missing)}")
    return None


async def after_confirm(db, activity_id=None, sale=None, lines=(), **_):
    from app.modules.pharmacy.pharmacy.models import PharmacyControlledLog, PharmacyPrescription

    drugs = await _drugs(db, lines)
    given = dict(sale.extra or {})
    rx_lines = [line for line in lines if drugs[line.product_id][1].get("requires_prescription")
                or drugs[line.product_id][1].get("is_controlled")]
    if not rx_lines and not given.get("rx_number"):
        return None
    if not given.get("rx_number"):
        given["rx_number"] = f"RX-{datetime.now():%Y%m%d}-{uuid.uuid4().hex[:4].upper()}"
        sale.extra = given
    total = sum(float(line.qty) * float(line.unit_price) - float(line.discount or 0) for line in rx_lines)
    db.add(PharmacyPrescription(
        rx_number=given["rx_number"], patient_name=given.get("patient_name") or "—",
        doctor_name=given.get("doctor_name") or "—", doctor_license=given.get("doctor_license"),
        patient_national_id=given.get("patient_national_id"), total_amount=total, patient_paid=total,
        status="dispensed", sale_id=sale.id,
    ))
    for line in rx_lines:
        name, extra = drugs[line.product_id]
        if not extra.get("is_controlled"):
            continue
        batches = (line.extra or {}).get("batches") or [{"batch_number": (line.extra or {}).get("batch_number") or "—",
                                                          "qty": float(line.qty)}]
        for b in batches:
            db.add(PharmacyControlledLog(
                product_id=line.product_id, sale_id=sale.id, batch_number=b.get("batch_number") or "—",
                patient_name=given.get("patient_name") or "—", patient_national_id=given.get("patient_national_id") or "—",
                prescriber_doctor=given.get("doctor_name") or "—", doctor_license=given.get("doctor_license"),
                quantity=int(round(float(b["qty"]))), transaction_type="dispense",
                notes=f"فاتورة {sale.invoice_number} — روشتة {given['rx_number']}",
            ))
    return given["rx_number"]
